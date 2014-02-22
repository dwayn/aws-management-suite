__author__ = 'dwayn'
import time
import types
import datetime
import re

import boto.ec2
from amslib.core.manager import BaseManager

from amslib.ssh.sshmanager import SSHManager
from errors import *


class SnapshotSchedule:
    def __init__(self):
        self.schedule_id = None
        self.hostname = None
        self.instance_id = None
        self.mount_point = None
        self.volume_group_id = None
        self.interval_hour = 1
        self.interval_day = 1
        self.interval_week = 1
        self.interval_month = 1
        self.retain_hourly = 24
        self.retain_daily = 14
        self.retain_weekly = 4
        self.retain_monthly = 12
        self.retain_yearly = 3
        self.pre_command = None
        self.post_command = None
        self.description = None


class SnapshotManager(BaseManager):

    def __get_boto_conn(self, region):
        if region not in self.__boto_conns:
            self.__boto_conns[region] = boto.ec2.connect_to_region(region, aws_access_key_id=self.settings.AWS_ACCESS_KEY, aws_secret_access_key=self.settings.AWS_SECRET_KEY)
        return self.__boto_conns[region]


    # pre_command and post_command can be a string containing a command to run using sudo on host, or they can be a callable function
    # if they are callable then these named parameters will be passed in:  hostname, instance_id
    # note that the pre/post commands will not be executed if the volume group is not attached to a host
    def snapshot_volume_group(self, volume_group_id, description=None, pre_command=None, post_command=None, expiry_date=None):
        # lookup volume_group and instance_id (if attached)
        self.__db.execute("select "
                          "vg.volume_group_id, "
                          "vg.raid_level, "
                          "vg.stripe_block_size, "
                          "vg.fs_type, "
                          "vg.block_device, "
                          "vg.group_type, "
                          "vg.tags, "
                          "hv.instance_id, "
                          "hv.mount_point, "
                          "v.availability_zone, "
                          "h.host "
                          "from "
                          "volume_groups vg "
                          "left join host_volumes hv on vg.volume_group_id = hv.volume_group_id "
                          "left join hosts h on h.instance_id = hv.instance_id "
                          "left join volumes v on v.volume_group_id=vg.volume_group_id "
                          "where vg.volume_group_id = %s", (volume_group_id, ))
        vgdata = self.__db.fetchone()
        if not vgdata:
            raise VolumeGroupNotFound("Volume group {0} not found".format(volume_group_id))

        region = vgdata[9][0:len(vgdata[9]) - 1]
        botoconn = self.__get_boto_conn(region)

        self.__db.execute("select volume_id, size, piops, block_device, raid_device_id, tags from volumes where volume_group_id=%s", (volume_group_id, ))
        voldata = self.__db.fetchall()
        if not voldata:
            raise VolumeGroupNotFound("Error fetching volume information for volume group {0}".format(volume_group_id))

        # check if volumes are attached
        volume_ids = []
        for v in voldata:
            volume_ids.append(v[0])
        vols = botoconn.get_all_volumes(volume_ids)

        attached = 0
        for v in vols:
            if v.attachment_state() == "attached":
                attached += 1

        if attached and (attached != len(vols)):
            raise VolumeMountError("Volumes in volume_group_id {0} are partially attached, halting snapshot")


        # run precommand
        if attached:
            if isinstance(pre_command, types.FunctionType):
                pre_command(hostname=vgdata[10], instance_id=vgdata[7])
            elif isinstance(pre_command, types.StringType):
                sh = SSHManager()
                sh.connect(hostname=vgdata[10], port=self.settings.SSH_PORT, username=self.settings.SSH_USER, password=self.settings.SSH_PASSWORD, key_filename=self.settings.SSH_KEYFILE)
                stdout, stderr, exit_code = sh.sudo(pre_command, sudo_password=self.settings.SUDO_PASSWORD)
                if int(exit_code) != 0:
                    raise SnapshotError("There was an error running snapshot pre_command\n{0}\n{1}".format(pre_command, stderr))


        # start snapshot on each volume
        snaps = {}
        snapshots = []
        for vol in voldata:
            snap = botoconn.create_snapshot(volume_id=vol[0], description=description)
            snaps[vol[0]] = snap
            snapshotdata = self.get_snapshot_struct(snap.id, vol[1], vol[4], vol[0], region, vol[3], vol[2], None, vol[5])
            snapshots.append(snapshotdata)


        # check to see if any of the snaps errored out
        for vid in snaps.keys():
            snaps[vid].update()
            if snaps[vid].status == 'error':
                raise SnapshotCreateError("There was an error creating snapshot {0} for volume_group_id: {1}".format(snaps[vid].id, volume_group_id))

        # store the metadata for the snapshot group
        self.store_snapshot_group(snapshots, volume_group_id, vgdata[3], vgdata[1], vgdata[2], vgdata[4], vgdata[6], expiry_date)

        # run postcommand
        if attached:
            if isinstance(post_command, types.FunctionType):
                post_command(hostname=vgdata[10], instance_id=vgdata[7])
            elif isinstance(post_command, types.StringType):
                sh = SSHManager()
                sh.connect(hostname=vgdata[10], port=self.settings.SSH_PORT, username=self.settings.SSH_USER, password=self.settings.SSH_PASSWORD, key_filename=self.settings.SSH_KEYFILE)
                stdout, stderr, exit_code = sh.sudo(post_command, sudo_password=self.settings.SUDO_PASSWORD)
                if int(exit_code) != 0:
                    raise SnapshotError("There was an error running snapshot post_command\n{0}\n{1}".format(post_command, stderr))



    # clones a group of snapshots that represent a snapshot group and creates a new volume group
    # TODO find out if growing the volumes will cause issues with the software raid
    def clone_snapshot_group(self, snapshot_group_id, zone, piops=None):
        # lookup the snapshot_group_id
        # check the state of each snapshot; error if not all in good state
        # clone each of the snapshots to volumes
        # write the data for a new volume_group
        # return the new volume_group_id


        pass


    def store_snapshot_group(self, snapshots, volume_group_id, filesystem, raid_level=0, stripe_block_size=256, block_device=None, tags=None, expiry_date=None):
        expdate = None
        raid_type = 'raid'
        if len(snapshots) == 1:
            raid_type = 'single'
        self.__db.execute("INSERT INTO snapshot_groups(volume_group_id, raid_level, stripe_block_size, fs_type, block_device, group_type, tags) "
                          "VALUES(%s,%s,%s,%s,%s,%s,%s)", (volume_group_id, raid_level, stripe_block_size, filesystem, block_device, raid_type, tags))
        self.__dbconn.commit()
        snapshot_group_id = self.__db.lastrowid

        print snapshot_group_id

        for x in range(0, len(snapshots)):
            snapshots[x]['snapshot_group_id'] = snapshot_group_id
            print snapshots[x]

            if expiry_date:
                expdate = expiry_date.strftime('%Y-%m-%d %H:%M:%S')
            self.__db.execute("INSERT INTO snapshots(snapshot_id, snapshot_group_id, volume_id, size, piops, block_device, raid_device_id, region, tags, expiry_date)"
                              "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (snapshots[x]['snapshot_id'], snapshots[x]['snapshot_group_id'], snapshots[x]['volume_id'],
                                                                    snapshots[x]['size'], snapshots[x]['piops'], snapshots[x]['block_device'], snapshots[x]['raid_device_id'],
                                                                    snapshots[x]['region'], snapshots[x]['tags'], expdate))
            self.__dbconn.commit()


        return snapshot_group_id


    def schedule_snapshot(self, schedule):
        if not isinstance(schedule, SnapshotSchedule):
            raise SnapshotScheduleError("SnapshotSchedule object required")
        insert_vars = []
        sql = 'INSERT INTO snapshot_schedules set'
        if schedule.hostname:
            insert_vars.append(schedule.hostname)
            sql += " hostname=%s"
            if schedule.mount_point:
                insert_vars.append(schedule.mount_point)
                sql += ", mount_point=%s"
            else:
                raise SnapshotScheduleError("Expecting mount_point to be set when using hostname to schedule a snapshot")
        elif schedule.instance_id:
            insert_vars.append(schedule.instance_id)
            sql += " instance_id=%s"
            if schedule.mount_point:
                insert_vars.append(schedule.mount_point)
                sql += ", mount_point=%s"
            else:
                raise SnapshotScheduleError("Expecting mount_point to be set when using instance_id to schedule a snapshot")
        elif schedule.volume_group_id:
            insert_vars.append(schedule.volume_group_id)
            sql += " volume_group_id=%s"
        else:
            raise SnapshotScheduleError("A snapshot must be scheduled for an instance_id, hostname or volume_group_id")

        sql += ', interval_hour=%s, interval_day=%s, interval_week=%s, interval_month=%s, retain_hourly=%s, retain_daily=%s, retain_weekly=%s, retain_monthly=%s, retain_yearly=%s, pre_command=%s, post_command=%s, description=%s'
        insert_vars.append(schedule.interval_hour)
        insert_vars.append(schedule.interval_day)
        insert_vars.append(schedule.interval_week)
        insert_vars.append(schedule.interval_month)
        insert_vars.append(schedule.retain_hourly)
        insert_vars.append(schedule.retain_daily)
        insert_vars.append(schedule.retain_weekly)
        insert_vars.append(schedule.retain_monthly)
        insert_vars.append(schedule.retain_yearly)
        insert_vars.append(schedule.pre_command)
        insert_vars.append(schedule.post_command)
        insert_vars.append(schedule.description)

        self.__db.execute(sql, insert_vars)
        self.__dbconn.commit()
        schedule.schedule_id = self.__db.lastrowid
        return schedule

    def delete_snapshot_schedule(self, schedule_id):
        self.__db.execute("delete from snapshot_schedules where schedule_id=%s",(schedule_id, ))
        self.__dbconn.commit()

    def edit_snapshot_schedule(self, schedule_id, updates):
        sql = "update snapshot_schedules set "
        update_vars = []
        sets = []
        for name in updates.keys():
            if name in ('pre_command', 'post_command', 'description') and updates[name] == "":
                updates[name] = None
            sets.append(str(name) + "=%s")
            update_vars.append(updates[name])

        sql += ', '.join(sets)
        sql += " where schedule_id=%s"
        update_vars.append(schedule_id)
        self.__db.execute(sql, update_vars)
        self.__dbconn.commit()


    def run_snapshot_schedule(self, schedule_id=None):
        t = datetime.datetime.today()
        sql = "select " \
                  "schedule_id," \
                  "h.host," \
                  "h.instance_id," \
                  "hv.volume_group_id," \
                  "hv.mount_point," \
                  "ss.volume_group_id," \
                  "interval_hour," \
                  "interval_day," \
                  "interval_week," \
                  "interval_month," \
                  "retain_hourly," \
                  "retain_daily," \
                  "retain_weekly," \
                  "retain_monthly," \
                  "retain_yearly," \
                  "pre_command," \
                  "post_command," \
                  "description " \
                  "from snapshot_schedules ss " \
                  "left join hosts h on h.instance_id=ss.instance_id or h.host=ss.hostname " \
                  "left join host_volumes hv on hv.instance_id=h.instance_id and hv.mount_point=ss.mount_point"

        if schedule_id:
            self.__db.execute(sql + " where schedule_id=%s", (schedule_id, ))
            schedules = self.__db.fetchall()
            if not schedules:
                print "Schedule not found"
                return
        else:
            self.__db.execute(sql)
            schedules = self.__db.fetchall()
            if not schedules:
                print "No snapshot schedules found"
                return

        for schedule in schedules:
            expiry_date = None

            # hourly snapshot
            if t.hour % schedule[6] == 0:
                expiry_date = t + datetime.timedelta(hours=schedule[6]*schedule[10])

            # daily snapshot
            if t.hour == 0 and t.day % schedule[7] == 0:
                expiry_date = t + datetime.timedelta(days=schedule[7]*schedule[11])

            # weekly snapshot
            if t.hour == 0 and t.weekday() == 0 and t.isocalendar()[1] % schedule[8] == 0:
                expiry_date = t + datetime.timedelta(weeks=schedule[8]*schedule[12])

            # monthly snapshot
            if t.hour == 0 and t.day == 1 and t.month % schedule[9] == 0:
                expiry_date = t + datetime.timedelta(days=schedule[9]*schedule[13]*30)

            # yearly snapshot
            if t.hour == 0 and t.day == 1 and t.month == 1:
                expiry_date = t + datetime.timedelta(days=schedule[14]*365)

            # if the snapshot should be done then an expiry_date should have been set, or if it was a manual snapshot then kick off the snapshot
            if expiry_date or schedule_id:
                if schedule[5]:
                    volume_group_id = schedule[5]
                else:
                    volume_group_id = schedule[3]

                self.snapshot_volume_group(volume_group_id=volume_group_id, description=schedule[17], pre_command=schedule[15], post_command=schedule[16], expiry_date=expiry_date)


    def get_snapshot_struct(self, snapshot_id, size, raid_device_id, volume_id, region, block_device=None, piops=None, snapshot_group_id=None, tags=None):
        struct = {
            'snapshot_id': snapshot_id,
            'snapshot_group_id': snapshot_group_id,
            'volume_id': volume_id,
            'size': size,
            'piops': piops,
            'block_device': block_device,
            'raid_device_id': raid_device_id,
            'region': region,
            'tags': tags
        }

        return struct

