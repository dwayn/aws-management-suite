__author__ = 'dwayn'
import time
import types
import datetime
import re

import boto.ec2
from amslib.core.manager import BaseManager
from amslib.ssh.sshmanager import SSHManager
from errors import *



class VolumeManager(BaseManager):

    def __get_boto_conn(self, region):
        if region not in self.__boto_conns:
            self.__boto_conns[region] = boto.ec2.connect_to_region(region, aws_access_key_id=self.settings.AWS_ACCESS_KEY, aws_secret_access_key=self.settings.AWS_SECRET_KEY)
        return self.__boto_conns[region]


    # provisions ebs volumes, attaches them to a host and create the software raid on the instance
    def create_volume_group(self, instance_id, num_volumes, per_volume_size, filesystem='xfs', raid_level=0, stripe_block_size=256, piops=None, tags=None, mount_point=None, automount=True):
        #TODO add support to hosts to know if iops are/can be enabled
        self.__db.execute("SELECT availability_zone, host from hosts where instance_id=%s", (instance_id, ))
        data = self.__db.fetchone()
        if not data:
            raise InstanceNotFound("Instance {0} not found; unable to lookup availability zone or host for instance".format(instance_id))

        volume_type = 'standard'
        if piops:
            volume_type = 'io1'


        availability_zone, host = data
        region = availability_zone[0:len(availability_zone) - 1]
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
        print "Waiting on volumes to become available"
        while not available:
            available = True
            for v in vols:
                v.update()
                if v.volume_state() == 'creating':
                    available = False
                elif v.volume_state() == 'error':
                    raise VolumeNotAvailable("Error creating volume {}".format(v.id))
            time.sleep(2)

        # and available software raid device will be picked when the raid is assembled
        volume_group_id = self.store_volume_group(volumes, filesystem, raid_level, stripe_block_size, None, tags)


        self.attach_volume_group(instance_id, volume_group_id)
        self.assemble_raid(instance_id, volume_group_id, True)
        if mount_point:
            self.mount_volume_group(instance_id, volume_group_id, mount_point, automount)
        return volume_group_id




    def attach_volume_group(self, instance_id, volume_group_id):
        self.__db.execute("select "
                          "v.volume_id, "
                          "v.availability_zone "
                          "from volume_groups vg join volumes v on vg.volume_group_id = v.volume_group_id "
                          "where vg.volume_group_id=%s "
                          "order by raid_device_id", (volume_group_id, ))
        data = self.__db.fetchall()

        if not data:
            raise VolumeGroupNotFound("Metadata not found for volume_group_id: {0}".format(volume_group_id))

        availability_zone = data[0][1]
        region = availability_zone[0:len(availability_zone) - 1]
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
                    print "Volume {0} not finished creating"
                    volumes_ready = False
                elif vol.status in ('in-use', 'deleting', 'deleted', 'error'):
                    raise VolumeNotAvailable("Volume {0} in volume_group {1} cannot be attached to instance. Current status: {2}".format(vol.id, volume_group_id, vol.status))



        instance = botoconn.get_only_instances([instance_id])[0]
        block_devices_in_use = []
        for dev in instance.block_device_mapping:
            block_devices_in_use.append(str(dev))


        dev_letter = 'f'
        for row in data:
            block_device = '/dev/sd' + dev_letter
            while block_device in block_devices_in_use:
                dev_letter = chr(ord(dev_letter) + 1)
                block_device = '/dev/sd' + dev_letter
            block_devices_in_use.append(block_device)

            print "Attaching {0} as {1} to {2}".format(vol.id, block_device, instance_id)
            volumes[row[0]].attach(instance_id, block_device)
            self.__db.execute("UPDATE volumes set block_device=%s where volume_id=%s", (block_device, row[0]))
            self.__dbconn.commit()


        print "Waiting for volumes to attach"
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

        #TODO need to discover if the disks got attached at sd* or xvd* and rewrite the data in mysql








    def assemble_raid(self, instance_id, volume_group_id, new_raid=False):
        #TODO check that the volumes are attached
        self.__db.execute("SELECT availability_zone, host from hosts where instance_id=%s", (instance_id, ))
        data = self.__db.fetchone()
        if not data:
            raise InstanceNotFound("Instance {0} not found; unable to lookup availability zone or host for instance".format(instance_id))
        availability_zone, host = data
        region = availability_zone[0:len(availability_zone) - 1]

        self.__db.execute("select "
                          "vg.raid_level, "
                          "vg.stripe_block_size, "
                          "vg.fs_type, "
                          "vg.group_type, "
                          "v.volume_id, "
                          "v.block_device, "
                          "v.raid_device_id "
                          "from volume_groups vg join volumes v on vg.volume_group_id = v.volume_group_id "
                          "where vg.volume_group_id=%s order by raid_device_id", (volume_group_id, ))
        voldata = self.__db.fetchall()

        if not voldata:
            raise VolumeGroupNotFound("Metadata not found for volume_group_id: {0}".format(volume_group_id))

        if voldata[0][3] != 'raid':
            print "No raid to assemble for single volume"
            return

        sh = SSHManager()
        sh.connect(hostname=host, port=self.settings.SSH_PORT, username=self.settings.SSH_USER, password=self.settings.SSH_PASSWORD, key_filename=self.settings.SSH_KEYFILE)

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
        for row in voldata:
            devcount += 1
            devlist += row[5] + " "
        fs_type = voldata[0][2]

        if new_raid:
            raid_level = voldata[0][0]
            stripe_block_size = voldata[0][1]
            command = 'mdadm --create {0} --level={1} --chunk={2} --raid-devices={3} {4}'.format(block_device, raid_level, stripe_block_size, devcount, devlist)
            stdout, stderr, exit_code = sh.sudo(command=command, sudo_password=self.settings.SUDO_PASSWORD)
            if int(exit_code) != 0:
                raise RaidError("There was an error creating raid with command:\n{0}\n{1}".format(command, stderr))

            command = 'mkfs.{0} {1}'.format(fs_type, block_device)
            stdout, stderr, exit_code = sh.sudo(command=command, sudo_password=self.settings.SUDO_PASSWORD)
            if int(exit_code) != 0:
                raise RaidError("There was an error creating filesystem with command:\n{0}\n{1}".format(command, stderr))

        else:
            command = 'mdadm --assemble {0} {1}'.format(block_device, devlist)
            stdout, stderr, exit_code = sh.sudo(command=command, sudo_password=self.settings.SUDO_PASSWORD)
            if int(exit_code) != 0:
                raise RaidError("There was an error creating raid with command:\n{0}\n{1}".format(command, stderr))

        #TODO add check in here to cat /proc/mdstat and make sure the expected raid is setup

        self.__db.execute("INSERT INTO host_volumes set instance_id=%s, volume_group_id=%s, mount_point=NULL ON DUPLICATE KEY UPDATE mount_point=NULL", (instance_id, volume_group_id))
        self.__db.execute("UPDATE volume_groups set block_device=%s where volume_group_id=%s", (block_device, volume_group_id))
        self.__dbconn.commit()





    def mount_volume_group(self, instance_id, volume_group_id, mount_point='/data', automount=True):
        #TODO at some point these should probably be configurable
        #TODO check that volume group is attached and assembled
        mount_options = 'noatime,nodiratime,noauto'

        self.__db.execute("select "
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
        data = self.__db.fetchone()
        if not data:
            raise VolumeGroupNotFound("Instance {0} not found; unable to lookup availability zone or host for instance".format(instance_id))

        cur_mount_point, host, availability_zone, block_device, volume_group_type, fs_type = data
        region = availability_zone[0:len(availability_zone) - 1]

        sh = SSHManager()
        sh.connect(hostname=host, port=self.settings.SSH_PORT, username=self.settings.SSH_USER, password=self.settings.SSH_PASSWORD, key_filename=self.settings.SSH_KEYFILE)
        #TODO mkdir -p of the mount directory
        command = "mkdir -p {}".format(mount_point)
        stdout, stderr, exit_code = sh.sudo(command=command, sudo_password=self.settings.SUDO_PASSWORD)
        if int(exit_code) != 0:
            raise VolumeMountError("Unable to create mount directory: {}".format(mount_point))
        command = 'mount {0} {1} -o {2}'.format(block_device, mount_point, mount_options)
        stdout, stderr, exit_code = sh.sudo(command=command, sudo_password=self.settings.SUDO_PASSWORD)
        if int(exit_code) != 0:
            raise VolumeMountError("Error mounting volume with command: {0}\n{1}".format(command, stderr))

        self.__db.execute("UPDATE host_volumes SET mount_point=%s WHERE instance_id=%s AND volume_group_id=%s", (mount_point, instance_id, volume_group_id))
        self.__dbconn.commit()

        print "Volume group {0} mounted on {1} ({2}) at {3}".format(volume_group_id, host, instance_id, mount_point)

        #TODO add the entries to to /etc/mdadm.conf so the raid device is initialized on boot
        if automount:
             self.configure_volume_automount(volume_group_id, mount_point)


    # updates /etc/fstab and /etc/mdadm.conf (if needed) to allow volumes to automatically mount on instance reboot
    # if mount_point is not given, then it will attempt to use a mount point that the volume group is mounted at
    # if a volume group has been attached and is mounted manually on the host then this will try to determine the
    # mount point, set that mount point in fstab, and save the mount point setting to the database
    def configure_volume_automount(self, volume_group_id, mount_point=None):
        mount_options = "noatime,nodiratime 0 0"
        block_device_match_pattern = '^({})\s+([^\s]+?)\s+([^\s]+?)\s+([^\s]+?)\s+([0-9])\s+([0-9]).*'
        self.__db.execute("select "
                          "hv.mount_point, "
                          "host, "
                          "vg.block_device, "
                          "vg.group_type, "
                          "vg.fs_type "
                          "from hosts h "
                          "join host_volumes hv on h.instance_id=hv.instance_id and hv.volume_group_id=%s "
                          "join volume_groups vg on vg.volume_group_id=hv.volume_group_id", (volume_group_id, ))
        info = self.__db.fetchone()
        if not info:
            raise VolumeMountError("instance_id, volume_group_id, or host_volume association not found")

        defined_mount_point, host, block_device, group_type, fs_type = info
        if not block_device:
            raise VolumeMountError("block device is not set for volume group {}, check that the volume group is attached".format(volume_group_id))

        sh = SSHManager()
        sh.connect(hostname=host, port=self.settings.SSH_PORT, username=self.settings.SSH_USER, password=self.settings.SSH_PASSWORD, key_filename=self.settings.SSH_KEYFILE)

        if not mount_point:
            if defined_mount_point:
                mount_point = defined_mount_point
            else:
                stdout, stderr, exit_code = sh.sudo('cat /etc/mtab')
                mtab = stdout.split("\n")
                for line in mtab:
                    m = re.match(block_device_match_pattern.format(block_device.replace('/', '\\/')), line)
                    if m:
                        mount_point = m.group(2)
                        break

        if not mount_point:
            raise VolumeMountError("No mount point defined and none can be determined for volume group".format(volume_group_id))

        new_fstab_line = "{} {} {} {}".format(block_device, mount_point, fs_type, mount_options)
        stdout, stderr, exit_code = sh.sudo('cat /etc/fstab')
        fstab = stdout.split("\n")
        found = False
        for i in range(0, len(fstab)):
            line = fstab[i]
            m = re.match(block_device_match_pattern.format(block_device.replace('/', '\\/')), line)
            if m:
                fstab[i] = new_fstab_line
                found = True
                break
        if not found:
            fstab.append(new_fstab_line)

        stdout, stderr, exit_code = sh.sudo("mv -f /etc/fstab /etc/fstab.prev")
        sh.sudo("echo '{}' >> /etc/fstab".format("\n".join(fstab)))
        sh.sudo("chmod 0644 /etc/fstab")

        self.__db.execute("update host_volumes set mount_point=%s where volume_group_id=%s", (mount_point, volume_group_id))
        self.__dbconn.commit()

        # at this point /etc/fstab is fully configured

        # if problems on debian (or other OS's), there may be more steps needed to get mdadm to autostart
        # http://superuser.com/questions/287462/how-can-i-make-mdadm-auto-assemble-raid-after-each-boot
        #'^({})\s+([^\s]+?)\s+([^\s]+?)\s+([^\s]+?)\s+([0-9])\s+([0-9]).*'
        if group_type == 'raid':
            print "Reading /etc/mdadm.conf"
            stdout, stderr, exit_code = sh.sudo("cat /etc/mdadm.conf")
            conf = stdout.split("\n")
            print "Reading current mdadm devices"
            stdout, stderr, exit_code = sh.sudo("mdadm --detail --scan ")
            scan = stdout.split("\n")

            mdadm_line = None
            for line in scan:
                m = re.match('^ARRAY\s+([^\s]+)\s.*', line)
                if m and m.group(1) == block_device:
                    mdadm_line = m.group(0)

            if not mdadm_line:
                raise VolumeMountError("mdadm --detail --scan did not return an mdadm configuration for {}".format(block_device))

            found = False
            for i in range(0, len(conf)):
                line = conf[i]
                m = re.match('^ARRAY\s+([^\s]+)\s.*', line)
                if m and m.group(1) == block_device:
                    conf[i] = mdadm_line
                    found = True
                    break
            if not found:
                conf.append(mdadm_line)

            print "Backing up /etc/mdadm.conf to /etc/mdadm.conf.prev"
            sh.sudo('mv -f /etc/mdadm.conf /etc/mdadm.conf.prev')
            print "Writing new /etc/mdadm.conf file"
            for line in conf:
                sh.sudo("echo '{}' >> /etc/mdadm.conf".format(line))



    def store_volume_group(self, volumes, filesystem, raid_level=0, stripe_block_size=256, block_device=None, tags=None):
        raid_type = 'raid'
        if len(volumes) == 1:
            raid_type = 'single'
        self.__db.execute("INSERT INTO volume_groups(raid_level, stripe_block_size, fs_type, block_device, group_type, tags) "
                          "VALUES(%s,%s,%s,%s,%s,%s)", (raid_level, stripe_block_size, filesystem, block_device, raid_type, tags))
        self.__dbconn.commit()
        volume_group_id = self.__db.lastrowid

        print volume_group_id

        for x in range(0, len(volumes)):
            volumes[x]['volume_group_id'] = volume_group_id
            print volumes[x]
            self.__db.execute("INSERT INTO volumes(volume_id, volume_group_id, availability_zone, size, piops, block_device, raid_device_id, tags)"
                              "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)", (volumes[x]['volume_id'], volumes[x]['volume_group_id'], volumes[x]['availability_zone'],
                                                                  volumes[x]['size'],volumes[x]['piops'], volumes[x]['block_device'],
                                                                  volumes[x]['raid_device_id'], volumes[x]['tags']))
            self.__dbconn.commit()


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
            'tags': tags
        }
        return struct



