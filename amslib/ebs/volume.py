__author__ = 'dwayn'
import time
import re
import os
import boto.ec2
import argparse
from amslib.core.manager import BaseManager
from amslib.ssh.sshmanager import SSHManager
from errors import *



class VolumeManager(BaseManager):

    def __get_boto_conn(self, region):
        if region not in self.boto_conns:
            self.boto_conns[region] = boto.ec2.connect_to_region(region, aws_access_key_id=self.settings.AWS_ACCESS_KEY, aws_secret_access_key=self.settings.AWS_SECRET_KEY)
        return self.boto_conns[region]


    # provisions ebs volumes, attaches them to a host and create the software raid on the instance
    def create_volume_group(self, instance_id, num_volumes, per_volume_size, filesystem='xfs', raid_level=0, stripe_block_size=256, piops=None, tags=None, mount_point=None, automount=True):
        #TODO add support to hosts to know if iops are/can be enabled
        self.db.execute("SELECT availability_zone, host from hosts where instance_id=%s", (instance_id, ))
        data = self.db.fetchone()
        if not data:
            raise InstanceNotFound("Instance {0} not found; unable to lookup availability zone or host for instance".format(instance_id))

        volume_type = 'standard'
        if piops:
            volume_type = 'io1'


        availability_zone, host = data
        region = self.parse_region_from_availability_zone(availability_zone)
        botoconn = self.__get_boto_conn(region)
        instance = botoconn.get_only_instances([instance_id])[0]
        block_devices_in_use = []
        for dev in instance.block_device_mapping:
            block_devices_in_use.append(str(dev))


        vols = []
        volumes = []
        for x in range(0, num_volumes):
            vol = botoconn.create_volume(size=per_volume_size, zone=availability_zone, volume_type=volume_type, iops=piops)
            vols.append(vol)
            block_device = None
            volumes.append(self.get_volume_struct(vol.id, availability_zone, per_volume_size, x, block_device, piops, None, tags))
        available = False
        self.logger.info("Waiting on volumes to become available")

        while not available:
            available = True
            for v in vols:
                v.update()
                if v.volume_state() == 'creating':
                    available = False
                elif v.volume_state() == 'error':
                    raise VolumeNotAvailable("Error creating volume {0}".format(v.id))
            time.sleep(2)

        # and available software raid device will be picked when the raid is assembled
        volume_group_id = self.store_volume_group(volumes, filesystem, raid_level, stripe_block_size, None, tags)


        self.attach_volume_group(instance_id, volume_group_id)
        self.assemble_raid(instance_id, volume_group_id, True)
        if mount_point:
            self.mount_volume_group(instance_id, volume_group_id, mount_point, automount)
        return volume_group_id




    def attach_volume_group(self, instance_id, volume_group_id):
        self.db.execute("select "
                          "v.volume_id, "
                          "v.availability_zone "
                          "from volume_groups vg join volumes v on vg.volume_group_id = v.volume_group_id "
                          "where vg.volume_group_id=%s "
                          "order by raid_device_id", (volume_group_id, ))
        data = self.db.fetchall()

        if not data:
            raise VolumeGroupNotFound("Metadata not found for volume_group_id: {0}".format(volume_group_id))

        availability_zone = data[0][1]
        region = self.parse_region_from_availability_zone(availability_zone)
        botoconn = self.__get_boto_conn(region)
        vol_ids = []
        volumes = {}
        for row in data:
            vol_ids.append(row[0])

        volumes_ready = True
        vols = botoconn.get_all_volumes(vol_ids)
        for vol in vols:
            volumes[vol.id] = vol
            if vol.status != 'creating':
                volumes_ready = False
            elif vol.status in ('in-use', 'deleting', 'deleted', 'error'):
                raise VolumeNotAvailable("Volume {0} cannot be attached to instance. Current status: {1}".format(vol.id, vol.status))

        while not volumes_ready:
            time.sleep(5)
            volumes_ready = True
            for vol in vols:
                vol.update()
                if vol.status == 'creating':
                    self.logger.info("Volume {0} not finished creating")
                    volumes_ready = False
                elif vol.status in ('in-use', 'deleting', 'deleted', 'error'):
                    raise VolumeNotAvailable("Volume {0} in volume_group {1} cannot be attached to instance. Current status: {2}".format(vol.id, volume_group_id, vol.status))



        instance = botoconn.get_only_instances([instance_id])[0]
        block_devices_in_use = []
        for dev in instance.block_device_mapping:
            block_devices_in_use.append(str(dev))


        dev_letter = 'f'
        for row in data:
            block_device = '/dev/xvd' + dev_letter
            while block_device in block_devices_in_use:
                dev_letter = chr(ord(dev_letter) + 1)
                block_device = '/dev/xvd' + dev_letter
            block_devices_in_use.append(block_device)

            self.logger.info("Attaching {0} as {1} to {2}".format(vol.id, block_device, instance_id))
            volumes[row[0]].attach(instance_id, block_device)
            self.db.execute("UPDATE volumes set block_device=%s where volume_id=%s", (block_device, row[0]))
            self.dbconn.commit()


        self.logger.info("Waiting for volumes to attach")
        waiting = True
        while waiting:
            waiting = False
            for vol in vols:
                vol.update()
                if vol.attachment_state() == 'attaching':
                    waiting = True
                elif vol.attachment_state() in ('detaching', 'detached'):
                    raise VolumeNotAvailable("There was an error attaching {0} to {1}".format(vol.id, instance_id))
            time.sleep(5)
        self.db.execute("INSERT INTO host_volumes set instance_id=%s, volume_group_id=%s, mount_point=NULL ON DUPLICATE KEY UPDATE mount_point=NULL", (instance_id, volume_group_id))
        self.dbconn.commit()
        self.logger.info("Volumes attached")




    def assemble_raid(self, instance_id, volume_group_id, new_raid=False):
        #TODO check that the volumes are attached
        self.db.execute("SELECT availability_zone, host from hosts where instance_id=%s", (instance_id, ))
        data = self.db.fetchone()
        if not data:
            raise InstanceNotFound("Instance {0} not found; unable to lookup availability zone or host for instance".format(instance_id))
        availability_zone, host = data
        region = self.parse_region_from_availability_zone(availability_zone)

        self.db.execute("select "
                          "vg.raid_level, "
                          "vg.stripe_block_size, "
                          "vg.fs_type, "
                          "vg.group_type, "
                          "v.volume_id, "
                          "v.block_device, "
                          "v.raid_device_id "
                          "from volume_groups vg join volumes v on vg.volume_group_id = v.volume_group_id "
                          "where vg.volume_group_id=%s order by raid_device_id", (volume_group_id, ))
        voldata = self.db.fetchall()

        if not voldata:
            raise VolumeGroupNotFound("Metadata not found for volume_group_id: {0}".format(volume_group_id))

        sh = SSHManager()
        sh.connect(hostname=host, port=self.settings.SSH_PORT, username=self.settings.SSH_USER, password=self.settings.SSH_PASSWORD, key_filename=self.settings.SSH_KEYFILE)

        fs_type = voldata[0][2]

        if voldata[0][3] == 'raid':
            stdout, stderr, exit_code = sh.sudo('ls --color=never /dev/md[0-9]*', sudo_password=self.settings.SUDO_PASSWORD)
            d = stdout.split(' ')
            current_devices = []
            for i in d:
                if i: current_devices.append(str(i))

            # find an available md* block device that we can use for the raid
            md_id = 0
            block_device = "/dev/md" + str(md_id)
            while block_device in current_devices:
                md_id += 1
                block_device = "/dev/md" + str(md_id)

            devcount = 0
            devlist = ''
            md_dev_pattern = ''
            for row in voldata:
                devcount += 1
                devlist += row[5] + " "
                # /dev/sd
                md_dev_pattern = '([a-z]+{0}).*?'.format(row[5][6:]) + md_dev_pattern
            md_dev_pattern = '(md[0-9]+).*?' + md_dev_pattern

            if new_raid:
                raid_level = voldata[0][0]
                stripe_block_size = voldata[0][1]
                command = '/sbin/mdadm --create {0} --level={1} --chunk={2} --raid-devices={3} {4}'.format(block_device, raid_level, stripe_block_size, devcount, devlist)
                stdout, stderr, exit_code = sh.sudo(command=command, sudo_password=self.settings.SUDO_PASSWORD)
                if int(exit_code) != 0:
                    raise RaidError("There was an error creating raid with command:\n{0}\n{1}".format(command, stderr))

                command = '/sbin/mkfs.{0} {1}'.format(fs_type, block_device)
                stdout, stderr, exit_code = sh.sudo(command=command, sudo_password=self.settings.SUDO_PASSWORD)
                if int(exit_code) != 0:
                    raise RaidError("There was an error creating filesystem with command:\n{0}\n{1}".format(command, stderr))

            else:
                # find out if the raid was auto assembled as a new md device before trying to assemble it
                stdout, stderr, exit_code = sh.sudo('cat /proc/mdstat', sudo_password=self.settings.SUDO_PASSWORD)
                mdstat = stdout.split('\n')

                dev_found = None
                for line in mdstat:
                    m = re.match(md_dev_pattern, line)
                    if m:
                        dev_found = m.group(1)

                if dev_found:
                    self.logger.info("Waiting 10 seconds to allow raid device to get ready")
                    time.sleep(10)
                    block_device = '/dev/' + dev_found
                else:
                    command = '/sbin/mdadm --assemble {0} {1}'.format(block_device, devlist)
                    stdout, stderr, exit_code = sh.sudo(command=command, sudo_password=self.settings.SUDO_PASSWORD)
                    if int(exit_code) != 0:
                        raise RaidError("There was an error creating raid with command:\n{0}\n{1}".format(command, stderr))

        else:
            block_device = voldata[0][5]
            if new_raid:
                command = '/sbin/mkfs.{0} {1}'.format(fs_type, block_device)
                stdout, stderr, exit_code = sh.sudo(command=command, sudo_password=self.settings.SUDO_PASSWORD)
                if int(exit_code) != 0:
                    raise RaidError("There was an error creating filesystem with command:\n{0}\n{1}".format(command, stderr))


        #TODO add check in here to cat /proc/mdstat and make sure the expected raid is setup

        self.db.execute("INSERT INTO host_volumes set instance_id=%s, volume_group_id=%s, mount_point=NULL ON DUPLICATE KEY UPDATE mount_point=NULL", (instance_id, volume_group_id))
        self.db.execute("UPDATE volume_groups set block_device=%s where volume_group_id=%s", (block_device, volume_group_id))
        self.dbconn.commit()





    def mount_volume_group(self, instance_id, volume_group_id, mount_point=None, automount=True):
        #TODO at some point these should probably be configurable
        #TODO check that volume group is attached and assembled
        mount_options = 'noatime,nodiratime,noauto'
        block_device_match_pattern = '^({0})\s+([^\s]+?)\s+([^\s]+?)\s+([^\s]+?)\s+([0-9])\s+([0-9]).*'

        self.db.execute("select "
                          "hv.mount_point, "
                          "host, "
                          "h.availability_zone, "
                          "vg.block_device, "
                          "vg.group_type, "
                          "vg.fs_type "
                          "from host_volumes hv "
                          "join hosts h on h.instance_id=hv.instance_id "
                          "join volume_groups vg on vg.volume_group_id=hv.volume_group_id "
                          "where hv.instance_id=%s and hv.volume_group_id=%s", (instance_id, volume_group_id))
        data = self.db.fetchone()
        if not data:
            raise VolumeGroupNotFound("Instance {0} not found; unable to lookup availability zone or host for instance".format(instance_id))

        cur_mount_point, host, availability_zone, block_device, volume_group_type, fs_type = data
        region = self.parse_region_from_availability_zone(availability_zone)

        sh = SSHManager()
        sh.connect(hostname=host, port=self.settings.SSH_PORT, username=self.settings.SSH_USER, password=self.settings.SSH_PASSWORD, key_filename=self.settings.SSH_KEYFILE)

        if not mount_point:
            stdout, stderr, exit_code = sh.sudo('cat /etc/fstab', sudo_password=self.settings.SUDO_PASSWORD)
            mtab = stdout.split("\n")
            for line in mtab:
                m = re.match(block_device_match_pattern.format(block_device.replace('/', '\\/')), line)
                if m:
                    mount_point = m.group(2)
                    break
        if not mount_point:
            raise VolumeMountError("No mount point defined and none can be determined for volume group".format(volume_group_id))

        #TODO mkdir -p of the mount directory
        command = "mkdir -p {0}".format(mount_point)
        stdout, stderr, exit_code = sh.sudo(command=command, sudo_password=self.settings.SUDO_PASSWORD)
        if int(exit_code) != 0:
            raise VolumeMountError("Unable to create mount directory: {0} with error: {1}".format(mount_point, stderr))
        command = 'mount {0} {1} -o {2} -t {3}'.format(block_device, mount_point, mount_options, fs_type)
        stdout, stderr, exit_code = sh.sudo(command=command, sudo_password=self.settings.SUDO_PASSWORD)
        if int(exit_code) != 0:
            raise VolumeMountError("Error mounting volume with command: {0}\n{1}".format(command, stderr))

        self.db.execute("UPDATE host_volumes SET mount_point=%s WHERE instance_id=%s AND volume_group_id=%s", (mount_point, instance_id, volume_group_id))
        self.dbconn.commit()

        self.logger.info("Volume group {0} mounted on {1} ({2}) at {3}".format(volume_group_id, host, instance_id, mount_point))

        #TODO add the entries to to /etc/mdadm.conf so the raid device is initialized on boot
        if automount:
             self.configure_volume_automount(volume_group_id, mount_point)


    # updates /etc/fstab and /etc/mdadm.conf (if needed) to allow volumes to automatically mount on instance reboot
    # if mount_point is not given, then it will attempt to use a mount point that the volume group is mounted at
    # if a volume group has been attached and is mounted manually on the host then this will try to determine the
    # mount point, set that mount point in fstab, and save the mount point setting to the database
    def configure_volume_automount(self, volume_group_id, mount_point=None, remove=False):
        mount_options = "noatime,nodiratime 0 0"
        block_device_match_pattern = '^({0})\s+([^\s]+?)\s+([^\s]+?)\s+([^\s]+?)\s+([0-9])\s+([0-9]).*'
        self.db.execute("select "
                          "hv.mount_point, "
                          "host, "
                          "vg.block_device, "
                          "vg.group_type, "
                          "vg.fs_type "
                          "from hosts h "
                          "join host_volumes hv on h.instance_id=hv.instance_id and hv.volume_group_id=%s "
                          "join volume_groups vg on vg.volume_group_id=hv.volume_group_id", (volume_group_id, ))
        info = self.db.fetchone()
        if not info:
            raise VolumeMountError("instance_id, volume_group_id, or host_volume association not found")

        defined_mount_point, host, block_device, group_type, fs_type = info
        if not block_device:
            raise VolumeMountError("block device is not set for volume group {0}, check that the volume group is attached".format(volume_group_id))

        sh = SSHManager()
        sh.connect(hostname=host, port=self.settings.SSH_PORT, username=self.settings.SSH_USER, password=self.settings.SSH_PASSWORD, key_filename=self.settings.SSH_KEYFILE)

        if not remove:
            if not mount_point:
                if defined_mount_point:
                    mount_point = defined_mount_point
                else:
                    stdout, stderr, exit_code = sh.sudo('cat /etc/mtab', sudo_password=self.settings.SUDO_PASSWORD)
                    mtab = stdout.split("\n")
                    for line in mtab:
                        m = re.match(block_device_match_pattern.format(block_device.replace('/', '\\/')), line)
                        if m:
                            mount_point = m.group(2)
                            break
                        else:
                            # this handles the backwards compatibility of the switch from using /dev/sd* to using /dev/xvd*
                            m = re.match(block_device_match_pattern.format(block_device.replace('/dev/xvd', '/dev/sd').replace('/', '\\/')), line)
                            if m:
                                mount_point = m.group(2)
                                break

            if not mount_point:
                raise VolumeMountError("No mount point defined and none can be determined for volume group".format(volume_group_id))
        self.logger.info("Reading /etc/fstab")
        new_fstab_line = "{0} {1} {2} {3}".format(block_device, mount_point, fs_type, mount_options)
        stdout, stderr, exit_code = sh.sudo('cat /etc/fstab', sudo_password=self.settings.SUDO_PASSWORD)

        # Checking that stdout is not empty is a safety check to make sure that fstab does not get blown away in case there is some issue getting
        # current contents of fstab file. Based on an observed bug that effectively renders an instance useless on reboot
        # as /dev/pts doesn't get mounted so ssh does not work
        if stdout.strip():
            fstab = stdout.split("\n")
            found = False
            for i in range(0, len(fstab)):
                line = fstab[i]
                m = re.match(block_device_match_pattern.format(block_device.replace('/', '\\/')), line)
                if m:
                    if remove:
                        fstab[i] = ''
                    else:
                        fstab[i] = new_fstab_line
                    found = True
                    break
                else:
                    # this handles the backwards compatibility of the switch from using /dev/sd* to using /dev/xvd*
                    m = re.match(block_device_match_pattern.format(block_device.replace('/dev/xvd', '/dev/sd').replace('/', '\\/')), line)
                    if m:
                        if remove:
                            fstab[i] = ''
                        else:
                            fstab[i] = new_fstab_line
                        found = True
                        break

            if not found and not remove:
                fstab.append(new_fstab_line)
            self.logger.info("Copying /etc/fstab to /etc/fstab.prev")
            stdout, stderr, exit_code = sh.sudo("mv -f /etc/fstab /etc/fstab.prev", sudo_password=self.settings.SUDO_PASSWORD)
            self.logger.info("Writing out new /etc/fstab")
            sh.sudo("echo '{0}' > /etc/fstab".format("\n".join(fstab).replace("\n\n", "\n")), sudo_password=self.settings.SUDO_PASSWORD)
            sh.sudo("chmod 0644 /etc/fstab", sudo_password=self.settings.SUDO_PASSWORD)

        if not remove:
            self.db.execute("update host_volumes set mount_point=%s where volume_group_id=%s", (mount_point, volume_group_id))
            self.dbconn.commit()

        # at this point /etc/fstab is fully configured

        # if problems on debian (or other OS's), there may be more steps needed to get mdadm to autostart
        # http://superuser.com/questions/287462/how-can-i-make-mdadm-auto-assemble-raid-after-each-boot
        if group_type == 'raid':
            self.logger.info("Reading /etc/mdadm.conf")
            stdout, stderr, exit_code = sh.sudo("cat /etc/mdadm.conf", sudo_password=self.settings.SUDO_PASSWORD)
            conf = stdout.split("\n")
            if not remove:
                self.logger.info("Reading current mdadm devices")
                stdout, stderr, exit_code = sh.sudo("/sbin/mdadm --detail --scan ", sudo_password=self.settings.SUDO_PASSWORD)
                scan = stdout.split("\n")

                mdadm_line = None
                for line in scan:
                    m = re.match('^ARRAY\s+([^\s]+)\s.*', line)
                    if m:
                        if m.group(1) == block_device:
                            mdadm_line = m.group(0)
                        else:
                            stdout, stderr, exit_code = sh.sudo("ls -l --color=never {0}".format(m.group(1)) + " | awk '{print $NF}'", sudo_password=self.settings.SUDO_PASSWORD)
                            if stdout.strip():
                                if os.path.basename(stdout.strip()) == os.path.basename(block_device):
                                    mdadm_line = m.group(0).replace(m.group(1), block_device)

                if not mdadm_line:
                    raise VolumeMountError("mdadm --detail --scan did not return an mdadm configuration for {0}".format(block_device))

            found = False
            for i in range(0, len(conf)):
                line = conf[i]
                m = re.match('^ARRAY\s+([^\s]+)\s.*', line)
                if m and m.group(1) == block_device:
                    if remove:
                        conf[i] = ''
                    else:
                        conf[i] = mdadm_line
                    found = True
                    break
            if not found and not remove:
                conf.append(mdadm_line)

            self.logger.info("Copying /etc/mdadm.conf to /etc/mdadm.conf.prev")
            sh.sudo('mv -f /etc/mdadm.conf /etc/mdadm.conf.prev', sudo_password=self.settings.SUDO_PASSWORD)
            self.logger.info("Writing new /etc/mdadm.conf file")
            for line in conf:
                if line:
                    sh.sudo("echo '{0}' >> /etc/mdadm.conf".format(line), sudo_password=self.settings.SUDO_PASSWORD)



    def store_volume_group(self, volumes, filesystem, raid_level=0, stripe_block_size=256, block_device=None, tags=None, snapshot_group_id=None):
        raid_type = 'raid'
        if len(volumes) == 1:
            raid_type = 'single'
        self.db.execute("INSERT INTO volume_groups(raid_level, stripe_block_size, fs_type, block_device, group_type, tags, snapshot_group_id) "
                          "VALUES(%s,%s,%s,%s,%s,%s,%s)", (raid_level, stripe_block_size, filesystem, block_device, raid_type, tags, snapshot_group_id))
        self.dbconn.commit()
        volume_group_id = self.db.lastrowid

        self.logger.info("New volume_group_id: {0}".format(volume_group_id))

        for x in range(0, len(volumes)):
            volumes[x]['volume_group_id'] = volume_group_id
            self.logger.debug(volumes[x])
            self.db.execute("INSERT INTO volumes(volume_id, volume_group_id, availability_zone, size, piops, block_device, raid_device_id, tags)"
                              "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)", (volumes[x]['volume_id'], volumes[x]['volume_group_id'], volumes[x]['availability_zone'],
                                                                  volumes[x]['size'],volumes[x]['piops'], volumes[x]['block_device'],
                                                                  volumes[x]['raid_device_id'], volumes[x]['tags']))
            self.dbconn.commit()


        return volume_group_id


    def get_volume_struct(self, volume_id, availability_zone, size, raid_device_id, block_device=None, piops=None, volume_group_id=None, tags=None):
        struct = {
            'volume_id': volume_id,
            'volume_group_id': volume_group_id,
            'availability_zone': availability_zone,
            'size': size,
            'piops': piops,
            'block_device': block_device,
            'raid_device_id': raid_device_id,
            'tags': tags,
        }
        return struct

    def unmount_volume_group(self, volume_group_id):

        self.db.execute("select "
                          "hv.mount_point, "
                          "host, "
                          "hv.instance_id, "
                          "h.availability_zone, "
                          "vg.block_device, "
                          "vg.group_type, "
                          "vg.fs_type "
                          "from host_volumes hv "
                          "join hosts h on h.instance_id=hv.instance_id "
                          "join volume_groups vg on vg.volume_group_id=hv.volume_group_id "
                          "where hv.volume_group_id=%s", (volume_group_id, ))
        data = self.db.fetchone()
        if not data:
            raise VolumeGroupNotFound("Record for volume group {0} not found".format(volume_group_id))

        cur_mount_point, host, instance_id, availability_zone, block_device, volume_group_type, fs_type = data

        sh = SSHManager()
        sh.connect(hostname=host, port=self.settings.SSH_PORT, username=self.settings.SSH_USER, password=self.settings.SSH_PASSWORD, key_filename=self.settings.SSH_KEYFILE)
        block_device_match_pattern = '^([^\s]+?)\s+([^\s]+?)\s+([^\s]+?)\s+([^\s]+?)\s+([0-9])\s+([0-9]).*'

        stdout, stderr, exit_code = sh.sudo('cat /etc/mtab', sudo_password=self.settings.SUDO_PASSWORD)
        mtab = stdout.split("\n")
        block_device_to_unmount = None
        for line in mtab:
            m = re.match(block_device_match_pattern, line)
            if m:
                if volume_group_type == 'single':
                    if m.group(1) == block_device:
                        block_device_to_unmount = m.group(1)
                    elif m.group(1).replace('/dev/hd', '/dev/xvd') == block_device:
                        block_device_to_unmount = m.group(1)
                    elif m.group(1).replace('/dev/sd', '/dev/xvd') == block_device:
                        block_device_to_unmount = m.group(1)
                else:
                    if m.group(1) == block_device:
                        block_device_to_unmount = m.group(1)


        if block_device_to_unmount:
            command = 'umount {0}'.format(block_device_to_unmount)
            stdout, stderr, exit_code = sh.sudo(command=command, sudo_password=self.settings.SUDO_PASSWORD)
            if int(exit_code) != 0:
                raise VolumeMountError("Error unmounting volume with command: {0}\n{1}".format(command, stderr))
            self.logger.info("Volume group {0} unmounted from host {1} ".format(volume_group_id, host))
        else:
            self.logger.warning("Volume group {0} is not mounted ".format(volume_group_id))

        self.db.execute("UPDATE host_volumes SET mount_point=%s WHERE instance_id=%s AND volume_group_id=%s", (None, instance_id, volume_group_id))
        self.dbconn.commit()


    def detach_volume_group(self, volume_group_id, force=False):
        self.db.execute("select "
                        "instance_id, "
                        "host, "
                        "mount_point, "
                        "v.availability_zone, "
                        "vg.group_type, "
                        "vg.block_device, "
                        "v.block_device, "
                        "volume_id "
                        "from volume_groups vg "
                        "join volumes v using(volume_group_id) "
                        "left join host_volumes hv using(volume_group_id) "
                        "left join hosts h using(instance_id) "
                        "where volume_group_id=%s", (volume_group_id,))

        voldata = self.db.fetchall()
        if not voldata:
            raise VolumeGroupNotFound("Volume group {0} not found".format(volume_group_id))

        instance_id, host, mount_point, availability_zone, volume_type, block_device = voldata[0][:6]

        if mount_point and not force:
            raise VolumeMountError("Volume group {0} is currently mounted on {1}, not detaching".format(volume_group_id, mount_point))

        if not host and not force:
            raise VolumeNotAvailable("Volume group {0} does not appear to be attached, use force option to force the detachment")

        if volume_type == 'raid' and host:
            sh = SSHManager()
            sh.connect(hostname=host, port=self.settings.SSH_PORT, username=self.settings.SSH_USER, password=self.settings.SSH_PASSWORD, key_filename=self.settings.SSH_KEYFILE)
            command = '/sbin/mdadm --stop {0}'.format(block_device)
            stdout, stderr, exit_code = sh.sudo(command=command, sudo_password=self.settings.SUDO_PASSWORD)
            if int(exit_code) != 0:
                raise VolumeMountError("Error stopping the software raid on volume group {0} with command: {1}\n{2}".format(volume_group_id, command, stderr))

        volids = []
        for d in voldata:
            volids.append(d[7])

        region = self.parse_region_from_availability_zone(availability_zone)
        botoconn = self.__get_boto_conn(region)
        vols = botoconn.get_all_volumes(volids)


        success = True
        for vol in vols:
            if vol.status == 'in-use':
                detached = vol.detach(force)
                if not detached:
                    success = False

        if success:
            self.configure_volume_automount(volume_group_id, None, True)
            self.db.execute("delete from host_volumes where volume_group_id=%s", (volume_group_id, ))
            self.dbconn.commit();
            self.logger.info("Volume group {0} detached from instance {1}".format(volume_group_id, instance_id))
        else:
            self.logger.info("Volume group {0} not detached".format(volume_group_id))


    def delete_volume_group(self, volume_group_id):
        self.db.execute("select "
                        "instance_id, "
                        "host, "
                        "mount_point, "
                        "v.availability_zone, "
                        "v.block_device, "
                        "volume_id "
                        "from volume_groups vg "
                        "join volumes v using(volume_group_id) "
                        "left join host_volumes hv using(volume_group_id) "
                        "left join hosts h using(instance_id) "
                        "where volume_group_id=%s", (volume_group_id,))

        voldata = self.db.fetchall()
        if not voldata:
            raise VolumeGroupNotFound("Cannot find volume group {0}".format(volume_group_id))

        instance_id, host, mount_point, availability_zone = voldata[0][:4]

        if mount_point:
            raise VolumeMountError("Volume group {0} is currently mounted on {1}, not deleting".format(volume_group_id, mount_point))
        if instance_id:
            raise VolumeMountError("Volume group {0} is currently attached to instance {1}, detach first before deleting".format(volume_group_id, instance_id))

        volids = []
        for d in voldata:
            volids.append(d[5])

        region = self.parse_region_from_availability_zone(availability_zone)
        botoconn = self.__get_boto_conn(region)
        vols = botoconn.get_all_volumes(volids)

        waiting = True
        while waiting:
            waiting = False
            for vol in vols:
                vol.update()
                time.sleep(.5)
                if vol.attachment_state() == 'detaching':
                    waiting = True
                elif vol.attachment_state() in ('attaching', 'attached'):
                    raise VolumeNotAvailable("Volumes are currently attached or attaching, not deleting")
            if waiting:
                self.logger.info("Waiting for volumes to detach")
            time.sleep(5)

        success = True
        for vol in vols:
            if vol.status in ('error', 'available'):
                deleted = vol.delete()
                if not deleted:
                    success = False
            elif vol.status in ('deleted', 'deleting'):
                self.logger.info("Volume {0} is already deleted, skipping".format(vol.id))
            else:
                raise VolumeNotAvailable("Volume {0} not in a state that it can currently be deleted. Current state: {1}".format(vol.id, vol.status))

        if success:
            self.db.execute("insert into deleted_volume_groups select * from volume_groups where volume_group_id=%s", (volume_group_id, ))
            self.db.execute("insert into deleted_volumes select * from volumes where volume_group_id=%s", (volume_group_id, ))
            self.db.execute("delete from volume_groups where volume_group_id=%s", (volume_group_id, ))
            self.db.execute("delete from volumes where volume_group_id=%s", (volume_group_id, ))
            self.dbconn.commit()
            self.logger.info("Volume group {0} deleted".format(volume_group_id, instance_id))
        else:
            self.logger.info("Volume group {0} not deleted (or not fully deleted)".format(volume_group_id))


    def discovery(self):
        self.logger.error("Volume discovery not implemented yet")


    def argument_parser_builder(self, parser):

        vsubparser = parser.add_subparsers(title="action", dest='action')

        # ams volume list
        vlistparser = vsubparser.add_parser("list")
        vlistparser.add_argument('search_field', nargs="?", help="field to search", choices=['host', 'instance_id'])
        vlistparser.add_argument('field_value', nargs="?", help="exact match search value")
        vlistparser.add_argument("--like", help="search string to use when listing resources")
        vlistparser.add_argument("--prefix", help="search string prefix to use when listing resources")
        vlistparser.add_argument("--zone", help="Availability zone to filter results by. This is a prefix search so any of the following is valid with increasing specificity: 'us', 'us-west', 'us-west-2', 'us-west-2a'")
        vlistparser.set_defaults(func=self.command_volume_list)


        # ams volume create
        vcreateparser = vsubparser.add_parser("create", help="Create new volume group.")
        vcreategroup = vcreateparser.add_mutually_exclusive_group(required=True)
        vcreategroup.add_argument('-i', '--instance', help="instance_id of an instance to attach new volume group")
        vcreategroup.add_argument('-H', '--host', help="hostname of an instance to attach new volume group")
        vcreateparser.add_argument('-n', '--numvols', type=int, help="Number of EBS volumes to create for the new volume group", required=True)
        vcreateparser.add_argument('-r', '--raid-level', type=int, help="Set the raid level for new EBS raid", default=0, choices=[0,1,5,10])
        vcreateparser.add_argument('-b', '--stripe-block-size', type=int, help="Set the stripe block/chunk size for new EBS raid", default=256)
        vcreateparser.add_argument('-m', '--mount-point', help="Set the mount point for volume. Not required, but suggested")
        vcreateparser.add_argument('-a', '--no-automount', help="Disable configuring the OS to automatically mount the volume group on reboot", action='store_true')
        #TODO should filesystem be a limited list?
        vcreateparser.add_argument('-f', '--filesystem', help="Filesystem to partition new raid/volume (currently only support filesystems that can be partitioned using mkfs.XXX)", default="xfs")
        vcreateparser.add_argument('-s', '--size', type=int, help="Per EBS volume size in GiBs", required=True)
        vcreateparser.add_argument('-p', '--iops', type=int, help="Per EBS volume provisioned iops")
        vcreateparser.set_defaults(func=self.command_volume_create)


        # ams volume attach
        vattachparser = vsubparser.add_parser("attach", help="Attach, assemble (if necessary) and mount(optional) a volume group")
        vattachparser.add_argument('volume_group_id', type=int, help="ID of the volume group to attach to instance")
        vattachgroup = vattachparser.add_mutually_exclusive_group(required=True)
        vattachgroup.add_argument('-i', '--instance', help="instance_id of an instance to attach new volume group")
        vattachgroup.add_argument('-H', '--host', help="hostname of an instance to attach new volume group")
        vattachparser.add_argument('-m', '--mount-point', help="Set the mount point for volume. Not required, but suggested")
        vattachparser.add_argument('-a', '--no-automount', help="Disable configuring the OS to automatically mount the volume group on reboot", action='store_true')
        vattachparser.set_defaults(func=self.command_volume_attach)


        # ams volume detach
        vdetachparser = vsubparser.add_parser("detach", help="Detach a volume group from an instance")
        vdetachparser.set_defaults(func=self.command_volume_detach)
        detachdefaultsparser = argparse.ArgumentParser(add_help=False)
        detachdefaultsparser.add_argument('-u', '--unmount', help="Unmounts the volume group if it is mounted. If this option is not included and the volume is mounted the detach operation will fail", action='store_true')
        detachdefaultsparser.add_argument('-f', '--force', help="Force detach the volume group's EBS volumes")
        vdetachsubparser = vdetachparser.add_subparsers(title='type', dest='type')
        # ams volume detach volume
        vdetachvolumeparser = vdetachsubparser.add_parser("volume", help="Detach a volume_group_id from the instance that it is currently attached", parents=[detachdefaultsparser])
        vdetachvolumeparser.add_argument('volume_group_id', type=int, help="ID of the volume group to detach")
        # ams volume detach host
        vdetachhostparser = vdetachsubparser.add_parser("host", help="Detach a volume group from a mount point on a host", parents=[detachdefaultsparser])
        vdetachhostparser.add_argument("hostname", help="Hostname")
        vdetachhostparser.add_argument("mount_point", help="Mount point of the volume to detach")
        # ams volume detach instance
        vdetachhostparser = vdetachsubparser.add_parser("instance", help="Detach a volume group from a mount point on an instance", parents=[detachdefaultsparser])
        vdetachhostparser.add_argument("instance_id", help="Instance ID")
        vdetachhostparser.add_argument("mount_point", help="Mount point of the volume to detach")


        # ams volume mount
        vmountparser = vsubparser.add_parser("mount", help="Mount a volume group and configure auto mounting with /etc/fstab (and /etc/mdadm.conf if needed). Volume group must already be attached to an instance")
        vmountparser.add_argument('volume_group_id', type=int, help="ID of the volume group to mount")
        vmountparser.add_argument('-m', '--mount-point', help="Set the mount point for volume. If not provided, will attempt to use currently defined mount point in /etc/fstab")
        vmountparser.add_argument('-a', '--no-automount', help="Disable configuring the OS to automatically mount the volume group on reboot", action='store_true')
        vmountparser.set_defaults(func=self.command_volume_mount)


        # ams volume unmount
        vumountparser = vsubparser.add_parser("unmount", help="Unmount a volume group")
        vumountparser.add_argument('volume_group_id', type=int, help="ID of the volume group to unmount")
        #TODO add support for host/mount_point unmounting for better UI
        #vumountparser.add_argument('-m', '--mount-point', help="Set the mount point for volume. If not provided, will attempt to use currently defined mount point")
        vumountparser.set_defaults(func=self.command_volume_unmount)


        # ams volume automount
        vmountparser = vsubparser.add_parser("automount", help="Configure auto mounting of volume group with /etc/fstab (and /etc/mdadm.conf if needed)")
        vmountparser.add_argument('volume_group_id', type=int, help="ID of the volume group to configure automount for")
        vmountparser.add_argument('-m', '--mount-point', help="Set the mount point for volume. If not provided, will attempt to use currently defined mount point")
        vmountparser.add_argument('-r', '--remove', help="Remove the current automount configuration for a volume group", action='store_true')
        vmountparser.set_defaults(func=self.command_volume_automount)


        # ams volume delete
        vdeleteparser = vsubparser.add_parser("delete", help="Delete a volume group")
        vdeleteparser.add_argument('volume_group_id', type=int, help="ID of the volume group to delete")
        vdeleteparser.set_defaults(func=self.command_volume_delete)

        # ams volume discovery
        vdiscoverparser = vsubparser.add_parser("discovery", help="Run discovery on volumes to populate the database with volumes")
        vdiscoverparser.set_defaults(func=self.command_volume_discover)


    def command_volume_discover(self, args):
        self.discovery()


    def command_volume_list(self, args):
        whereclauses = []
        order_by = ''
        if args.search_field:
            if args.search_field in ('host', 'instance_id'):
                args.search_field = "h." + args.search_field
            if args.field_value:
                whereclauses.append("{0} = '{1}'".format(args.search_field, args.field_value))
            elif args.like:
                whereclauses.append("{0} like '%{1}%'".format(args.search_field, args.like))
            elif args.prefix:
                whereclauses.append("{0} like '%{1}%'".format(args.search_field, args.prefix))
            order_by = ' order by {0}'.format(args.search_field)
        if args.zone:
            whereclauses.append("v.availability_zone like '{0}%'".format(args.zone))
            if not order_by:
                order_by = ' order by v.availability_zone'

        sql = "select " \
                "vg.volume_group_id, " \
                "v.availability_zone, " \
                "count(*) as volumes_in_group, " \
                "raid_level, " \
                "sum(size) as GiB, " \
                "piops, " \
                "h.instance_id, " \
                "h.host, " \
                "hv.mount_point, " \
                "vg.block_device " \
                "from " \
                "volume_groups vg " \
                "left join volumes v on v.volume_group_id=vg.volume_group_id " \
                "left join host_volumes hv on vg.volume_group_id=hv.volume_group_id " \
                "left join hosts h on h.instance_id=hv.instance_id "

        if len(whereclauses):
            sql += " where " + " and ".join(whereclauses)
        sql += " group by vg.volume_group_id"
        sql += order_by
        self.db.execute(sql)
        results = self.db.fetchall()

        headers = ["volume_group_id", "availability_zone", "volumes_in_group", "raid_level", "GiB", "iops", "instance_id", "hostname", "mount_point", "block_device"]
        self.output_formatted("Volume Groups", headers, results)



    def command_volume_create(self, args):
        automount = True
        if args.no_automount:
            automount = False
        if args.instance:
            instance_id = args.instance
        elif args.host:
            self.db.execute("select instance_id from hosts where host=%s", (args.host, ))
            row = self.db.fetchone()
            if not row:
                self.logger.error("Host {0} not found".format(args.host))
                return
            instance_id = row[0]

        self.create_volume_group(instance_id, args.numvols, args.size, args.filesystem, args.raid_level, args.stripe_block_size, args.iops, None, args.mount_point, automount)

    def command_volume_attach(self, args):
        instance_id = None
        if args.instance:
            self.db.execute("select instance_id from hosts where instance_id=%s",(args.instance, ))
            row = self.db.fetchone()
            if not row:
                self.logger.error("Instance ID {0} not recognized, try adding the host".format(args.instance))
                return
            instance_id = row[0]
        elif args.host:
            self.db.execute("select instance_id from hosts where host=%s",(args.host, ))
            row = self.db.fetchone()
            if not row:
                self.logger.error("Instance ID not found for host: {0}".format(args.host))
                return
            instance_id = row[0]

        self.attach_volume_group(instance_id, args.volume_group_id)
        self.assemble_raid(instance_id, args.volume_group_id, False)
        automount = True
        if args.no_automount:
            automount = False
        if args.mount_point:
            self.mount_volume_group(instance_id, args.volume_group_id, args.mount_point, automount)


    def command_volume_detach(self, args):
        volume_group_id = None
        if args.type == 'volume':
            volume_group_id = args.volume_group_id
        elif args.type == 'host':
            self.db.execute("select volume_group_id from hosts h join host_volumes hv using(instance_id) where host=%s and mount_point=%s", (args.hostname, args.mount_point))
            row = self.db.fetchone()
            if not row:
                self.logger.error("volume group not found for {0} on {1}".format(args.hostname, args.mount_point))
                return
            volume_group_id = row[0]
        elif args.type == 'instance':
            self.db.execute("select volume_group_id from hosts h join host_volumes hv using(instance_id) where instance_id=%s and mount_point=%s", (args.instance_id, args.mount_point))
            row = self.db.fetchone()
            if not row:
                self.logger.error("volume group not found for {0} on {1}".format(args.instance_id, args.mount_point))
                return
            volume_group_id = row[0]

        if args.unmount:
            self.unmount_volume_group(volume_group_id)
        self.detach_volume_group(volume_group_id, args.force)


    def command_volume_automount(self, args):
        self.configure_volume_automount(args.volume_group_id, args.mount_point, args.remove)

    def command_volume_mount(self, args):
        self.db.execute("select instance_id from host_volumes where volume_group_id=%s", (args.volume_group_id, ))
        row = self.db.fetchone()
        if not row:
            raise InstanceNotFound("Volume group {0} does not appear to be attached to an instance, attach the volume group to an instance first".format(args.volume_group_id))

        instance_id = row[0]
        self.mount_volume_group(instance_id, args.volume_group_id, args.mount_point, not args.no_automount)

    def command_volume_unmount(self, args):
        self.unmount_volume_group(args.volume_group_id)

    def command_volume_delete(self, args):
        self.delete_volume_group(args.volume_group_id)

