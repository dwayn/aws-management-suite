__author__ = 'dwayn'
import time
import types
import datetime
import re
import argparse

import boto.ec2
from amslib.core.manager import BaseManager
from volume import VolumeManager
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

    # copy an entire snapshot group to a region
    def copy_snapshot_group(self, snapshot_group_id, region):

        pass


    # clones a group of snapshots that represent a snapshot group and creates a new volume group
    # TODO find out if growing the volumes will cause issues with the software raid
    def clone_snapshot_group(self, snapshot_group_id, zone, piops=None):
        region = zone[0:len(zone) - 1]
        botoconn = self.__get_boto_conn(region)
        self.__db.execute("select "
                          "snapshot_id, "
                          "volume_id, "
                          "size, "
                          "piops, "
                          "raid_device_id, "
                          "region, "
                          "sg.snapshot_group_id, "
                          "volume_group_id, "
                          "raid_level, "
                          "stripe_block_size, "
                          "fs_type, "
                          "group_type, "
                          "sg.block_device, "
                          "s.block_device "
                          "from snapshot_groups sg "
                          "left join snapshots s on s.snapshot_group_id=sg.snapshot_group_id "
                          "where sg.snapshot_group_id=%s", (snapshot_group_id, ))
        snapshot_group = self.__db.fetchall()
        if not snapshot_group:
            raise SnapshotNotFound("Snapshot group {} not found".format(snapshot_group_id))

        source_region = snapshot_group[0][5]
        volume_group_id = snapshot_group[0][7]
        raid_level = snapshot_group[0][8]
        stripe_block_size = snapshot_group[0][9]
        fs_type = snapshot_group[0][10]
        group_type = snapshot_group[0][11]

        # if the snapshot group is not in the same region as where the volume group is being created then it needs to be copied first
        if region != source_region:

            pass


        snapshot_ids = []
        for s in snapshot_group:
            snapshot_ids.append(s[0])

        snapshots = botoconn.get_all_snapshots(snapshot_ids)

        # check for errors and wait if snapshots are still pending
        #TODO need to decide if this should fail on pending snaps or wait...maybe an option to wait?
        ready = False
        while not ready:
            ready = True
            for s in snapshots:
                if s.status == 'error':
                    raise SnapshotError('Snapshot {} is in an error state, unable to clone snapshot group {}.'.format(s.id, snapshot_group_id))
                if s.status == 'pending':
                    ready = False

            if ready:
                break;
            else:
                for s in snapshots:
                    s.update()
                time.sleep(5)

        vm = VolumeManager()
        #vm.get_volume_struct()

        # clone each of the snapshots to volumes
        # make sure they do not error out before returning
        # write the data for the new volume group to the database
        # return new volume group id





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

    def argument_parser_builder(self, parser):
        ssubparser = parser.add_subparsers(title="action", dest='action')

        screateparser = ssubparser.add_parser("create", help="Create a snapshot group of a volume group")
        screatesubparser = screateparser.add_subparsers(title="resource", dest='resource')
        screatevolparser = screatesubparser.add_parser("volume", help="create a snapshot of a given volume_group_id")
        screatevolparser.add_argument('volume_group_id', type=int, help="ID of the volume group to snapshot")
        screatevolparser.add_argument("--pre", help="command to run on host to prepare for starting EBS snapshot (will not be run if volume group is not attached)")
        screatevolparser.add_argument("--post", help="command to run on host after snapshot (will not be run if volume group is not attached)")
        screatevolparser.add_argument("-d", "--description", help="description to add to snapshot(s)")
        screatevolparser.set_defaults(func=self.command_snapshot_create_volume)
        screatehostparser = screatesubparser.add_parser("host", help="create a snapshot of a specific volume group on a host")
        group = screatehostparser.add_mutually_exclusive_group(required=True)
        group.add_argument('-i', '--instance', help="instance_id of an instance to snapshot a volume group")
        group.add_argument('-H', '--host', help="hostname of an instance to snapshot a volume group")
        group = screatehostparser.add_mutually_exclusive_group(required=True)
        group.add_argument('-m', '--mount-point', help="mount point of the volume group to snapshot")
        screatehostparser.add_argument("--pre", help="command to run on host to prepare for starting EBS snapshot (will not be run if volume group is not attached)")
        screatehostparser.add_argument("--post", help="command to run on host after snapshot (will not be run if volume group is not attached)")
        screatehostparser.add_argument("-d", "--description", help="description to add to snapshot(s)")
        screatehostparser.set_defaults(func=self.command_snapshot_create_host)

        sscheduleparser = ssubparser.add_parser("schedule", help="View, add or edit snapshot schedules")
        sschedulesubparser = sscheduleparser.add_subparsers(title="subaction", dest='subaction')

        sschedulelistparser = sschedulesubparser.add_parser("list", help="List snapshot schedules")
        sschedulelistparser.add_argument('resource', nargs='?', help="host, instance, or volume", choices=['host', 'volume', 'instance'])
        sschedulelistparser.add_argument('resource_id', nargs='?', help="hostname, instance_id or volume_group_id")
        sschedulelistparser.add_argument("--like", help="search string to use when listing resources")
        sschedulelistparser.add_argument("--prefix", help="search string prefix to use when listing resources")
        sschedulelistparser.set_defaults(func=self.command_snapshot_schedule_list)


        scheduleaddshared = argparse.ArgumentParser(add_help=False)
        scheduleaddshared.add_argument('-i', '--intervals', type=int, nargs=4, help='Set all intervals at once', metavar=('HOUR', 'DAY', 'WEEK', 'MONTH'))
        scheduleaddshared.add_argument('-r', '--retentions', type=int, nargs=5, help='Set all retentions at once', metavar=('HOURS', 'DAYS', 'WEEKS', 'MONTHS', 'YEARS'))
        scheduleaddshared.add_argument('--int_hour', dest="interval_hour", type=int, help="hourly interval for snapshots", metavar="HOURS")
        scheduleaddshared.add_argument('--int_day', dest="interval_day", type=int, help="daily interval for snapshots", metavar="DAYS")
        scheduleaddshared.add_argument('--int_week', dest="interval_week", type=int, help="weekly interval for snapshots", metavar="WEEKS")
        scheduleaddshared.add_argument('--int_month', dest="interval_month", type=int, help="monthly interval for snapshots", metavar="MONTHS")
        scheduleaddshared.add_argument('--ret_hour', dest="retain_hourly", type=int, help="number of hourly snapshots to keep", metavar="HOURS")
        scheduleaddshared.add_argument('--ret_day', dest="retain_daily", type=int, help="number of daily snapshots to keep", metavar="DAYS")
        scheduleaddshared.add_argument('--ret_week', dest="retain_weekly", type=int, help="number of weekly snapshots to keep", metavar="WEEKS")
        scheduleaddshared.add_argument('--ret_month', dest="retain_monthly", type=int, help="number of monthly snapshots to keep", metavar="MONTHS")
        scheduleaddshared.add_argument('--ret_year', dest="retain_yearly", type=int, help="number of yearly snapshots to keep", metavar="YEARS")
        scheduleaddshared.add_argument("--pre", dest="pre_command", help="command to run on host to prepare for starting EBS snapshot (will not be run if volume group is not attached)")
        scheduleaddshared.add_argument("--post", dest="post_command", help="command to run on host after snapshot (will not be run if volume group is not attached)")
        scheduleaddshared.add_argument('-d', "--description", help="description to add to snapshot")

        sscheduleaddparser = sschedulesubparser.add_parser("add", help="Create a new snapshot schedule")
        sscheduleaddparser.set_defaults(func=self.command_snapshot_schedule_add)
        sscheduleaddsubparser = sscheduleaddparser.add_subparsers(title="resource", dest="resource")
        sscheduleaddhostparser = sscheduleaddsubparser.add_parser("host", help="add a snapshot to the schedule for a specific hostname (recommended)", parents=[scheduleaddshared])
        sscheduleaddhostparser.add_argument("hostname", help="hostname to schedule snapshots for")
        group = sscheduleaddhostparser.add_mutually_exclusive_group(required=True)
        group.add_argument('-m', '--mount-point', help="mount point of the volume group to snapshot")
        sscheduleaddinstparser = sscheduleaddsubparser.add_parser("instance", help="add a snapshot to the schedule for a specific instance_id", parents=[scheduleaddshared])
        sscheduleaddinstparser.add_argument("instance_id", help="instance_id to schedule snapshots for")
        group = sscheduleaddinstparser.add_mutually_exclusive_group(required=True)
        group.add_argument('-m', '--mount-point', help="mount point of the volume group to snapshot")
        sscheduleaddinstparser = sscheduleaddsubparser.add_parser("volume", help="add a snapshot to the schedule for a specific volume_group_id", parents=[scheduleaddshared])
        sscheduleaddinstparser.add_argument("volume_group_id", help="volume_group_id to schedule snapshots for")

        sscheduleeditparser = sschedulesubparser.add_parser("edit", help="Edit a snapshot schedule. hostname, instance_id, volume_group_id, and mount_point cannot be edited", parents=[scheduleaddshared])
        sscheduleeditparser.add_argument('schedule_id', type=int, help="Snapshot schedule_id to edit (use 'ams snapshot schedule list' to list available schedules)")
        sscheduleeditparser.set_defaults(func=self.command_snapshot_schedule_edit)

        sscheduledelparser = sschedulesubparser.add_parser("delete", help="Delete a snapshot schedule", parents=[scheduleaddshared])
        sscheduledelparser.add_argument('schedule_id', type=int, help="Snapshot schedule_id to delete (use 'ams snapshot schedule list' to list available schedules)")
        sscheduledelparser.set_defaults(func=self.command_snapshot_schedule_delete)

        sschedulerunparser = sschedulesubparser.add_parser("run", help="Run the scheduled snapshots now")
        sschedulerunparser.add_argument('schedule_id', nargs='?', type=int, help="Snapshot schedule_id to run. If not supplied, then whatever is scheduled for the current time will run")
        sschedulerunparser.set_defaults(func=self.command_snapshot_schedule_run)




    def command_snapshot_create_volume(self, args):
        self.snapshot_volume_group(args.volume_group_id, args.description, args.pre, args.post)


    def command_snapshot_create_host(self, args):
        whereclauses = []
        if args.instance:
            whereclauses.append("h.instance_id = '{}'".format(args.instance))
        elif args.host:
            whereclauses.append("h.host = '{}'".format(args.host))

        if args.mount_point:
            whereclauses.append("hv.mount_point = '{}'".format(args.mount_point))

        sql = "select " \
              "hv.volume_group_id " \
              "from " \
              "hosts h " \
              "left join host_volumes hv on h.instance_id=hv.instance_id "
        sql += " where " + " and ".join(whereclauses)
        self.__db.execute(sql)
        res = self.__db.fetchone()
        if res:
            self.snapshot_volume_group(res[0], args.description, args.pre, args.post)
        else:
            print "Volume group not found"
            exit(1)

    def command_snapshot_schedule_list(self, args):
        whereclauses = []
        order_by = ''
        if args.resource == 'host':
            if args.resource_id:
                whereclauses.append("hostname = '{}'".format(args.resource_id))
            elif args.prefix:
                whereclauses.append("hostname like '{}%'".format(args.prefix))
            elif args.like:
                whereclauses.append("hostname like '%{}%'".format(args.like))
            order_by = " order by hostname asc"
        elif args.resource == 'instance':
            if args.resource_id:
                whereclauses.append("instance_id = '{}'".format(args.resource_id))
            elif args.prefix:
                whereclauses.append("instance_id like '{}%'".format(args.prefix))
            elif args.like:
                whereclauses.append("instance_id like '%{}%'".format(args.like))
            order_by = " order by instance_id asc"
        elif args.resource == 'volume':
            if args.resource_id:
                whereclauses.append("volume_group_id = {}".format(args.resource_id))

        sql = "select " \
              "schedule_id," \
              "hostname," \
              "instance_id," \
              "mount_point," \
              "volume_group_id," \
              "concat(interval_hour,'-',interval_day,'-',interval_week,'-',interval_month)," \
              "concat(retain_hourly,'-',retain_daily,'-',retain_weekly,'-',retain_monthly,'-',retain_yearly)," \
              "pre_command," \
              "post_command," \
              "description " \
              "from snapshot_schedules "
        if whereclauses:
            sql += " and ".join(whereclauses)
        sql += order_by
        self.__db.execute(sql)
        results = self.__db.fetchall()
        if self.settings.human_output:
            print "Snapshot Schedules:"
            print "schedule_id\thostname\tinstance_id\tmount_point\tvolume_group_id\tintervals(h-d-w-m)\tretentions(h-d-w-m-y)\tpre_command\tpost_command\tdescription"
            print "---------------------------------------------------------------------------------------------------------------------------------------------------"
        for res in results:
            print "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(res[0],res[1],res[2],res[3],res[4],res[5],res[6],res[7],res[8],res[9])
        if self.settings.human_output:
            print "---------------------------------------------------------------------------------------------------------------------------------------------------"


    def command_snapshot_schedule_add(self, args):
        schedule = SnapshotSchedule()
        processargs = [
            'interval_hour',
            'interval_day',
            'interval_week',
            'interval_month',
            'retain_hourly',
            'retain_daily',
            'retain_weekly',
            'retain_monthly',
            'retain_yearly',
            'description',
            'pre_command',
            'post_command',
        ]

        if args.resource == 'host':
            schedule.hostname = args.host
        if args.resource == 'instance':
            schedule.instance_id = args.instance_id
        if args.resource in ('host', 'instance'):
            schedule.mount_point = args.mount_point
        if args.resource == 'volume':
            schedule.volume_group_id = args.volume_group_id

        for arg in processargs:
            if getattr(args, arg):
                setattr(schedule, arg, getattr(args, arg))

        if args.intervals:
            schedule.interval_hour = args.intervals[0]
            schedule.interval_day = args.intervals[1]
            schedule.interval_week = args.intervals[2]
            schedule.interval_month = args.intervals[3]
        if args.retentions:
            schedule.retain_hourly = args.retentions[0]
            schedule.retain_daily = args.retentions[1]
            schedule.retain_weekly = args.retentions[2]
            schedule.retain_monthly = args.retentions[3]
            schedule.retain_yearly = args.retentions[4]

        self.schedule_snapshot(schedule)

    def command_snapshot_schedule_edit(self, args):
        processargs = [
            'interval_hour',
            'interval_day',
            'interval_week',
            'interval_month',
            'retain_hourly',
            'retain_daily',
            'retain_weekly',
            'retain_monthly',
            'retain_yearly',
            'description',
            'pre_command',
            'post_command',
        ]
        updates = {}

        for arg in processargs:
            if getattr(args, arg) is not None:
                updates[arg] = getattr(args, arg)

        if args.intervals:
            updates['interval_hour'] = args.intervals[0]
            updates['interval_day'] = args.intervals[1]
            updates['interval_week'] = args.intervals[2]
            updates['interval_month'] = args.intervals[3]
        if args.retentions:
            updates['retain_hourly'] = args.retentions[0]
            updates['retain_daily'] = args.retentions[1]
            updates['retain_weekly'] = args.retentions[2]
            updates['retain_monthly'] = args.retentions[3]
            updates['retain_yearly'] = args.retentions[4]

        if not len(updates):
            print "Must provide something to update on a snapshot schedule"
            return

        self.edit_snapshot_schedule(args.schedule_id, updates)


    def command_snapshot_schedule_delete(self, args):
        self.delete_snapshot_schedule(args.schedule_id)


    def command_snapshot_schedule_run(self, args):
        self.run_snapshot_schedule(args.schedule_id)

