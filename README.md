aws-management-suite
====================

Source URL: https://github.com/dwayn/aws-management-suite

# Introduction
This is currently very much a work in progress, and there is much that will be cleaned up and added over time. The goal of this suite is to
abstract many of the common tasks related to managing cloud infrastructure in AWS and bridge the gap
between raw infrastructure management tools like the EC2 command line tools, and configuration management tools. Initially, this tool
is focused on EBS volume, raid and snapshot management of single and raid volumes, but going forward the goal is to cover other infrastructure management needs
that are not fully addressed by other tools.

## Current Features
SSH client
* password or private key based login
* support for sudo login (password or passwordless)
* captures stdout, stderr and exit code from command run

EBS Volumes (managed as groups of volumes)
* create volume/raid
* delete volume/raid
* attach volume/raid
* detach volume/raid
* create software raid volume
* partition and format new volumes/raids
* (re)assemble software raid from existing (or newly cloned) ebs volumes
* mount volume/raid
* unmount volume/raid

EBS Snapshots (managed as groups of snapshots)
* pre/post snapshot hooks to enable running commands/scripts on target host before and after starting snapshot to ensure consistent point in time snapshot of all volumes in a raid group
* copy snapshot group to another region (only handled internally currently)
* clone snapshot group to new volume group and optionally attach/mount on a host
* clone latest snapshot of a volume group or host/instance + mount point
* schedule regular snapshots of volume/raid with managed grandfather/father/son expiration
* automatable purging of expired snapshots


Instance Management
* Instances can be manually added or edited using `ams host add` or `ams host edit` respectively
* Instance discovery has been implemented, allowing the hosts table to be automatically populated

Route53
* Discovery has been implemented to synchronize the local database with the current state of Route53 DNS records and health checks
* create raw DNS record
* create DNS record for a specific host without explicitly defining a number of the parameters that are on the host (optionally also configure a Route53 health check for the host)
* create Route53 health checks
* support for managing Simple, Weighted Round Robin, Failover, and Latency routing policies in Route53 records
* delete DNS record

## Setup and Configuration
### Initial installation
* This tool will only work on systems with python 2.6+ (due to paramiko requirements), but to date has only been tested on 2.6.6 and 2.7.6 but should run on any 2.6.x or 2.7.x version (3.x compatibility is unknown). If you find that it specifically does or does not work on any version please let me know and I will add it to this list.
* The tool requires ssh and sudo access to hosts in order to accomplish tasks like mounting volumes and running system commands to start/stop services (for snapshots)
* Copy sample_settings.py to settings.py and edit AWS, SSH and SUDO access credentials
* A MySQL database needs to be setup for tracking state. The following statements assume that the mysql database and the tool are located on the same host:
 * `CREATE DATABASE ams;` -- Create the schema
 * `GRANT ALL PRIVILEGES ON ams.* TO 'ams_user'@'localhost' IDENTIFIED BY 'mypass';` -- (This will create user with username 'ams_user' and password of 'mypass' and give access to the new schema created)
* Edit TRACKING_DB credentials in settings.py with the proper credentials for your MySQL database
* `pip install -r requirements.txt` will install the handful of external dependencies
 * You have option of either running pip install as root or if you have setup a virtualenv for this tool, then you you can run pip install without root in the virtual environment
 * Documentation on setting the tool up with virtualenv is planned for the future
* Suggested: add the path to ams directory to your path or add symlink to `ams` script to a directory in the system path
* `ams internals database install` will create the current full version of all of the tables

### Enabling bash/zsh completion
This project makes use of the argcomplete library (https://github.com/kislyuk/argcomplete) to provide dynamic completion. As part of the pip installation,
the library will be installed, but completion will still need to be enabled. Due to some multi-platform issues I experienced trying to enable global completeion,
I opted to use specific completion. All that is needed is to add this line to your .bashrc, .profile or .bash_profile (depending on which your OS uses) and then reload
your terminal or `source .bashrc` (or .profile or .bash_profile).

`eval "$(register-python-argcomplete ams)"`

### Upgrading
If you have updated the code base, just run `pip install -r requirements.txt` to install any new dependencies and run `ams internals database upgrade` to run the update scripts
for the database tables. Upgrade scripts can be run as often as you like, as it will do nothing if the database version matches the code version. If the database version is not
in sync with the current version defined in the tool, the tool will not allow any operations to be done until the internals database is upgraded; this is avoid the possiblity of
corrupting data in the database due to expectations in the software.



# Management Tool Usage

## General
All of the functionality is through the command line tool `ams`. It has been implemented as a multi-level nested command parser using the argparse module.<br>
If at any point you need help just add `-h` or `--help` flag to the command line and it will list all available sub-commands and options for the current command level.<br>
There are still a few legacy command structures that need to be cleaned up, so there may be some minor changes to the syntax to a few of these, but I will attempt to keep these to an absolute minimum.


## Host/Instance
#### `ams host list`
With no options this lists all host entries in the database

Arguments:

      --zone ZONE         Availability zone to filter results by. This is a prefix
                          search so any of the following is valid with increasing
                          specificity: 'us', 'us-west', 'us-west-2', 'us-west-2a'

----

#### `ams host list host [hostname]`
If `hostname` is given then it will match hostname exactly

Arguments:

      --like LIKE         wildcard matches hostname
      --prefix PREFIX     prefix matches hostname
      --zone ZONE         Availability zone to filter results by. This is a prefix
                          search so any of the following is valid with increasing
                          specificity: 'us', 'us-west', 'us-west-2', 'us-west-2a'


----

#### `ams host list instance [instance id]`
If `instance id` is given then it will match instance_id exactly

Arguments:

      --like LIKE         wildcard matches instance id
      --prefix PREFIX     prefix matches instance id
      --zone ZONE         Availability zone to filter results by. This is a prefix
                          search so any of the following is valid with increasing
                          specificity: 'us', 'us-west', 'us-west-2', 'us-west-2a'

----

#### `ams host add`
Add a host to the hosts table so that resources on the host can be managed. This has effectively been replaced by the host discovery functionality.

Required arguments: --instance, --host, --zone

Arguments:

      -i INSTANCE, --instance INSTANCE
                            Instance ID of the instance to add
      -u UNAME, --uname UNAME
                            Hostname to use when setting uname on the host
                            (default is to use instance hostname)
      -H HOSTNAME, --hostname HOSTNAME
                            hostname of the host (used to ssh to the host to do
                            management)
      -z ZONE, --zone ZONE  availability zone that the instance is in
      --hostname-internal HOSTNAME_INTERNAL
                            internal hostname (stored but not currently used)
      --hostname-external HOSTNAME_EXTERNAL
                            external hostname (stored but not currently used)
      --ip-internal IP_INTERNAL
                            internal IP address (stored but not currently used)
      --ip-external IP_EXTERNAL
                            external IP address (stored but not currently used)
      --ami-id AMI_ID       AMI ID (stored but not currently used)
      --instance-type INSTANCE_TYPE
                            Instance type (stored but not currently used)
      --notes NOTES         Notes on the instance/host (stored but not currently
                            used)
      -z ZONE, --zone ZONE  availability zone that the instance is in

----

#### `ams host edit`
Edit a host's details in the database, particularly useful for editing the hostname which does not get overwritten on discovery passes. Also provides
the option --configure-hostname which will ssh to the host and set the system hostname to the hostname that you have configured

Required arguments: --instance

Arguments:

      -i INSTANCE, --instance INSTANCE
                            Instance ID of the instance to add
      -u UNAME, --uname UNAME
                            Hostname to use when setting uname on the host
                            (default is to use instance hostname)
      --hostname-internal HOSTNAME_INTERNAL
                            internal hostname (stored but not currently used)
      --hostname-external HOSTNAME_EXTERNAL
                            external hostname (stored but not currently used)
      --ip-internal IP_INTERNAL
                            internal IP address (stored but not currently used)
      --ip-external IP_EXTERNAL
                            external IP address (stored but not currently used)
      --ami-id AMI_ID       AMI ID (stored but not currently used)
      --instance-type INSTANCE_TYPE
                            Instance type (stored but not currently used)
      --notes NOTES         Notes on the instance/host (stored but not currently
                            used)
      --name NAME           Name of the host (should match the 'Name' tag in EC2
                            for the instance)
      -H HOSTNAME, --hostname HOSTNAME
                            hostname of the host (used to ssh to the host to do
                            management)
      --configure-hostname  Set the hostname on the host to the FQDN that is
                            currently the hostname or the uname that is currently
                            defined for the instance in AMS (uname will override
                            FQDN)
      -z ZONE, --zone ZONE  availability zone that the instance is in

----

#### `ams host discovery`
Runs host discovery to populate the hosts table automatically

Arguments: None

----

## Volumes
#### `ams volume list`
With no options this lists all volume groups in the database

Arguments:

      --zone ZONE         Availability zone to filter results by. This is a prefix
                          search so any of the following is valid with increasing
                          specificity: 'us', 'us-west', 'us-west-2', 'us-west-2a'

----

#### `ams volume list host [hostname]`
Lists the volume groups for a host or hosts<br>
If `hostname` is given then it will match hostname exactly

Arguments:

      --like LIKE         wildcard matches hostname
      --prefix PREFIX     prefix matches hostname
      --zone ZONE         Availability zone to filter results by. This is a prefix
                          search so any of the following is valid with increasing
                          specificity: 'us', 'us-west', 'us-west-2', 'us-west-2a'


----

#### `ams volume list instance [instance_id]`
Lists the volume groups for an instance or instances<br>
If `instance id` is given then it will match instance_id exactly

Arguments:

      --like LIKE         wildcard matches instance id
      --prefix PREFIX     prefix matches instance id
      --zone ZONE         Availability zone to filter results by. This is a prefix
                          search so any of the following is valid with increasing
                          specificity: 'us', 'us-west', 'us-west-2', 'us-west-2a'


----

#### `ams volume create`
Creates a new volume group (single or multiple disk) and attaches to host. Optionally mounts the volume and configures automounting.

Required arguments: (--host | --instance), --numvols, --size

Defaults:

 * stripe-block-size: `256`  (256k chunk size recommended for performance of EBS stripes using xfs)
 * raid-level: `0`
 * filesystem: `xfs`  (note: currently due to implementation constrictions filesystem must be one of the types that can be formatted using mkfs.*)
 * iops: `None`
 * mount-point: `None`   (disk will not be mounted and automounting will not be configured if mount-point not provided)
 * no-automount: `false`  (automounting of volumes/raids will be configured in fstab and mdadm.conf by default unless explicitly disabled)


Arguments:

      -i INSTANCE, --instance INSTANCE
                            instance_id of an instance to attach new volume group
      -H HOST, --host HOST  hostname of an instance to attach new volume group
      -n NUMVOLS, --numvols NUMVOLS
                            Number of EBS volumes to create for the new volume
                            group
      -r {0,1,5,10}, --raid-level {0,1,5,10}
                            Set the raid level for new EBS raid
      -b STRIPE_BLOCK_SIZE, --stripe-block-size STRIPE_BLOCK_SIZE
                            Set the stripe block/chunk size for new EBS raid
      -m MOUNT_POINT, --mount-point MOUNT_POINT
                            Set the mount point for volume. Not required, but
                            suggested
      -a, --no-automount    Disable configuring the OS to automatically mount the
                            volume group on reboot
      -f FILESYSTEM, --filesystem FILESYSTEM
                            Filesystem to partition new raid/volume
      -s SIZE, --size SIZE  Per EBS volume size in GiBs
      -p IOPS, --iops IOPS  Per EBS volume provisioned iops

----

#### `ams volume delete (volume_group_id)`
Deletes provided volume_group_id. Volume group must not be currently attached to an instance.

Required arguments: volume_group_id


----

#### `ams volume attach (volume_group_id)`
Attaches provided volume_group_id to a host. Optionally mounts the volume and configures automounting.

Required arguments: volume_group_id, (--host | --instance)

Defaults:

 * mount-point: `None`   (disk will not be mounted and automounting will not be configured if mount-point not provided)
 * no-automount: `false`  (automounting of volumes/raids will be configured in fstab and mdadm.conf by default unless explicitly disabled)

Arguments:

      -i INSTANCE, --instance INSTANCE
                            instance_id of an instance to attach new volume group
      -H HOST, --host HOST  hostname of an instance to attach new volume group
      -m MOUNT_POINT, --mount-point MOUNT_POINT
                            Set the mount point for volume. Not required, but
                            suggested
      -a, --no-automount    Disable configuring the OS to automatically mount the
                            volume group on reboot

----

#### `ams volume detach volume (volume_group_id)`
Detaches provided volume_group_id from the host it is currently attached. Removes the automounting configuration for the volume group.

Required arguments: volume_group_id

Arguments:

      -u, --unmount         Unmounts the volume group if it is mounted. If this
                            option is not included and the volume is mounted the
                            detach operation will fail
      -f FORCE, --force FORCE
                            Force detach the volume group's EBS volumes

----

#### `ams volume detach host (hostname) (mount_point)`
Detaches provided volume group that is mounted at `mount_point` on `hostname`. Removes the automounting configuration for the volume group.

Required arguments: hostname, mount_point

Arguments:

      -u, --unmount         Unmounts the volume group if it is mounted. If this
                            option is not included and the volume is mounted the
                            detach operation will fail
      -f FORCE, --force FORCE
                            Force detach the volume group's EBS volumes

----

#### `ams volume detach instance (instance_id) (mount_point)`
Detaches provided volume group that is mounted at `mount_point` on `instance_id`. Removes the automounting configuration for the volume group.

Required arguments: instance_id, mount_point

Arguments:

      -u, --unmount         Unmounts the volume group if it is mounted. If this
                            option is not included and the volume is mounted the
                            detach operation will fail
      -f FORCE, --force FORCE
                            Force detach the volume group's EBS volumes

----

#### `ams volume mount (volume_group_id)`
Mount a volume group on the host that it is currently attached. Supports mounting to a given mount point or the currently defined mount point for the volume group.

Required arguments: volume_group_id

Arguments:

      -m MOUNT_POINT, --mount-point MOUNT_POINT
                            Set the mount point for volume. If not provided, will
                            attempt to use currently defined mount point
      -a, --no-automount    Disable configure the OS to automatically mount the
                            volume group on reboot

----

#### `ams volume unmount (volume_group_id)`
Unmount volume_group_id on the host that it is currently mounted. Does not make any changes to currently automount configuration.

Required arguments: volume_group_id



----

#### `ams volume automount (volume_group_id)`
Configure automounting for the volume_group_id. If mount point is not provided then it will use the currently defined mount point for the volume.
If neither of these exist then it will configure automounting of the volume where it is currently mounted, otherwise it will fail configuring automounting.

Required arguments: volume_group_id

Arguments:

      -m MOUNT_POINT, --mount-point MOUNT_POINT
                            Set the mount point for volume. If not provided, will
                            attempt to use currently defined mount point
      -r, --remove          Remove the current automount configuration for a
                            volume group

----

## Snapshots
#### `ams snapshot list volume (volume_group_id)`
List the snapshots of a specific volume_group_id.<br>

Required arguments: volume_group_id

Arguments:

      -r REGION, --region REGION
                            Filter the snapshots by region
      -x, --extended        Show more detailed information

----

#### `ams snapshot list host [hostname]`
List the snapshots for a specific host, or for hosts matching a search string. Optionally filter by mount point and/or region.<br>

Arguments:

      -m MOUNT_POINT, --mount-point MOUNT_POINT
                            Filter the snapshots by the mount point
      -r REGION, --region REGION
                            Filter the snapshots by region
      --like LIKE           search string to use to filter hosts
      --prefix PREFIX       search string prefix to filter hosts
      -x, --extended        Show more detailed information

----

#### `ams snapshot list instance [instance_id]`
List the snapshots for a specific instance, or for instances matching a search string. Optionally filter by mount point and/or region.<br>

Arguments:

      -m MOUNT_POINT, --mount-point MOUNT_POINT
                            Filter the snapshots by the mount point
      -r REGION, --region REGION
                            Filter the snapshots by region
      --like LIKE           search string to use to filter hosts
      --prefix PREFIX       search string prefix to filter hosts
      -x, --extended        Show more detailed information

----

#### `ams snapshot create volume (volume_group_id)`
Create a snapshot of a specific volume_group_id.<br>
PRE and POST are commands that will be run before and after the snapshot, and provide a means to ensure that data is in a
consistent state before snapshotting and revert back to normal operation after snapshot has begun.
Description is written as metadata to the snapshot itself and will show up in the EC2 console.

Required arguments: volume_group_id

Arguments:

      --pre PRE             command to run on host to prepare for starting EBS
                            snapshot (will not be run if volume group is not
                            attached)
      --post POST           command to run on host after snapshot (will not be run
                            if volume group is not attached)
      -d DESCRIPTION, --description DESCRIPTION
                            description to add to snapshot(s)
      --freeze              Issue an fsfreeze command to freeze and unfreeze the
                            filesystem of a volume when taking the snapshot

----

#### `ams snapshot create host`
Create a snapshot of a specific volume that is on a host<br>
PRE and POST are commands that will be run before and after the snapshot, and provide a means to ensure that data is in a
consistent state before snapshotting and revert back to normal operation after snapshot has begun.<br>
Description is written as metadata to the snapshot itself and will show up in the EC2 console.

Required arguments: (--host | --instance), --mount-point

Arguments:

      -i INSTANCE, --instance INSTANCE
                            instance_id of an instance to snapshot a volume group
      -H HOST, --host HOST  hostname of an instance to snapshot a volume group
      -m MOUNT_POINT, --mount-point MOUNT_POINT
                            mount point of the volume group to snapshot
      --pre PRE             command to run on host to prepare for starting EBS
                            snapshot (will not be run if volume group is not
                            attached)
      --post POST           command to run on host after snapshot (will not be run
                            if volume group is not attached)
      -d DESCRIPTION, --description DESCRIPTION
                            description to add to snapshot(s)
      --freeze              Issue an fsfreeze command to freeze and unfreeze the
                            filesystem of a volume when taking the snapshot

----

#### `ams snapshot delete expired`
Delete all expired snapshots. This operation is intended to be able to be added to crontab for regular purging of expired snapshots

Required arguments: None

Arguments: None

----

#### `ams snapshot delete snapshot (snapshot_group_id)`
Delete a specific snapshot_group_id. Use one of the snapshot list commands to find a snapshot_group_id.

Required arguments: snapshot_group_id

----

#### `ams snapshot clone snapshot (snapshot_group_id)`
Clone a specific snapshot_group_id into a new volume group and optionally attach and mount the new volume.<br>
This will manage copying snapshot to destination region if the destination region is not the same as where the snapshot group is held.<br>

If iops is provided then the volumes in the new volume group will be created with the provided iops, otherwise the iops of the original volume
group for the snapshot will be used. To create the volumes in the new volume group with no iops when the original volume group had iops,
pass in 0 for iops to explicitly disable.

Required arguments: snapshot_group_id, (--zone | --host | --instance)

Arguments:

      -z ZONE, --zone ZONE  Availability zone to create the new volume group in
      -i INSTANCE, --instance INSTANCE
                            instance id to attach the new volume group to
      -H HOST, --host HOST  hostname to attache the new volume group to
      -m MOUNT_POINT, --mount_point MOUNT_POINT
                            directory to mount the new volume group to
      -a, --no-automount    Disable configuring the OS to automatically mount the
                            volume group on reboot
      -p PIOPS, --iops PIOPS
                            Per EBS volume provisioned iops. Set to 0 to
                            explicitly disable provisioned iops. If not provided
                            then the iops of the original volumes will be used.

----

#### `ams snapshot clone latest volume (volume_group_id)`
Clone the latest snapshot for a volume_group_id and optionally attach and mount the new volume.<br>
This will manage copying snapshot to destination region if the destination region is not the same as where the snapshot group is held.<br>

If iops is provided then the volumes in the new volume group will be created with the provided iops, otherwise the iops of the original volume
group for the snapshot will be used. To create the volumes in the new volume group with no iops when the original volume group had iops,
pass in 0 for iops to explicitly disable.

Required arguments: volume_group_id, (--zone | --host | --instance)

Arguments:

      -z ZONE, --zone ZONE  Availability zone to create the new volume group in
      -i INSTANCE, --instance INSTANCE
                            instance id to attach the new volume group to
      -H HOST, --host HOST  hostname to attache the new volume group to
      -m MOUNT_POINT, --mount_point MOUNT_POINT
                            directory to mount the new volume group to
      -a, --no-automount    Disable configuring the OS to automatically mount the
                            volume group on reboot
      -p IOPS, --iops IOPS  Per EBS volume provisioned iops. Set to 0 to
                            explicitly disable provisioned iops. If not provided
                            then the iops of the original volumes will be used.


----

#### `ams snapshot clone latest host (hostname) (src_mount_point)`
Clone the latest snapshot for a host + mount-point and optionally attach and mount the new volume.<br>
This will manage copying snapshot to destination region if the destination region is not the same as where the snapshot group is held.<br>

If iops is provided then the volumes in the new volume group will be created with the provided iops, otherwise the iops of the original volume
group for the snapshot will be used. To create the volumes in the new volume group with no iops when the original volume group had iops,
pass in 0 for iops to explicitly disable.

Required arguments: hostname, src_mount_point, (--zone | --host | --instance)

Arguments:

      -z ZONE, --zone ZONE  Availability zone to create the new volume group in
      -i INSTANCE, --instance INSTANCE
                            instance id to attach the new volume group to
      -H HOST, --host HOST  hostname to attache the new volume group to
      -m MOUNT_POINT, --mount_point MOUNT_POINT
                            directory to mount the new volume group to
      -a, --no-automount    Disable configuring the OS to automatically mount the
                            volume group on reboot
      -p IOPS, --iops IOPS  Per EBS volume provisioned iops. Set to 0 to
                            explicitly disable provisioned iops. If not provided
                            then the iops of the original volumes will be used.

----

#### `ams snapshot clone latest instance (instance_id) (src_mount_point)`
Clone the latest snapshot for an instance + mount-point and optionally attach and mount the new volume.<br>
This will manage copying snapshot to destination region if the destination region is not the same as where the snapshot group is held.<br>

If iops is provided then the volumes in the new volume group will be created with the provided iops, otherwise the iops of the original volume
group for the snapshot will be used. To create the volumes in the new volume group with no iops when the original volume group had iops,
pass in 0 for iops to explicitly disable.

Required arguments: instance_id, src_mount_point, (--zone | --host | --instance)

Arguments:

      -z ZONE, --zone ZONE  Availability zone to create the new volume group in
      -i INSTANCE, --instance INSTANCE
                            instance id to attach the new volume group to
      -H HOST, --host HOST  hostname to attache the new volume group to
      -m MOUNT_POINT, --mount_point MOUNT_POINT
                            directory to mount the new volume group to
      -a, --no-automount    Disable configuring the OS to automatically mount the
                            volume group on reboot
      -p IOPS, --iops IOPS  Per EBS volume provisioned iops. Set to 0 to
                            explicitly disable provisioned iops. If not provided
                            then the iops of the original volumes will be used.


----

#### `ams snapshot schedule list [resource] [resource_id]`
Lists the snapshot schedules based on a specific resource id. `resource` is one of the literals `host`, `instance`, `volume`
and `resource_id` is either hostname, instance_id, or volume_group_d respectively.<br>
If no arguments are provided, then it will list all snapshot schedules


Arguments:

      --like LIKE           search string to use when listing resources
      --prefix PREFIX       search string prefix to use when listing resources

----

#### `ams snapshot schedule add host (hostname)`
Schedule snapshots for a host + mount point. This is the most flexible of the snapshot scheduling methods as it will resolve
the host and mount point to do snapshots and will not be affected if the instance or the volume group are changed on a host.<br>
Interval settings affect how often a snapshot is performed/retained. eg. 2 for hourly will take an "hourly" snapshot every other hour,
2 for daily will take a "daily" snapshot every other day.<br>
Retain settings affect how many of each type of snapshot to keep. eg. 24 for hours will keep the last 24 "hourly" snapshots
(not necessarily the last 24 hours if "hourly" interval is not 1). Setting the retain value for any of the types to 0 disables that one.<br>
If `--intervals` or `--retentions` are set, they will override the single `int_*` and `ret_*` arguments<br>
PRE and POST are commands that will be run before and after the snapshot, and provide a means to ensure that data is in a consistent state before
snapshotting and revert back to normal operation after snapshot has begun.<br>
Description is written as metadata to the snapshot itself and will show up in the EC2 console.

Required arguments: hostname, --mount-point

Defaults:
* int_hour  `1`
* int_day   `1`
* int_week  `1`
* int_month `1`
* ret_hour  `24`
* ret_day   `14`
* ret_week  `4`
* ret_month `12`
* ret_year  `3`

Arguments:

      -i HOUR DAY WEEK MONTH, --intervals HOUR DAY WEEK MONTH
                            Set all intervals at once
      -r HOURS DAYS WEEKS MONTHS YEARS, --retentions HOURS DAYS WEEKS MONTHS YEARS
                            Set all retentions at once
      --int_hour HOURS      hourly interval for snapshots
      --int_day DAYS        daily interval for snapshots
      --int_week WEEKS      weekly interval for snapshots
      --int_month MONTHS    monthly interval for snapshots
      --ret_hour HOURS      number of hourly snapshots to keep
      --ret_day DAYS        number of daily snapshots to keep
      --ret_week WEEKS      number of weekly snapshots to keep
      --ret_month MONTHS    number of monthly snapshots to keep
      --ret_year YEARS      number of yearly snapshots to keep
      --pre PRE_COMMAND     command to run on host to prepare for starting EBS
                            snapshot (will not be run if volume group is not
                            attached)
      --post POST_COMMAND   command to run on host after snapshot (will not be run
                            if volume group is not attached)
      -d DESCRIPTION, --description DESCRIPTION
                            description to add to snapshot
      -m MOUNT_POINT, --mount-point MOUNT_POINT
                            mount point of the volume group to snapshot


----

#### `ams snapshot schedule add instance (instance_id)`
Schedule snapshots for an instance + mount point. This is more flexible than the volume group id based snapshot, but if the instance
for a host is replaced, then the snapshot may not be able to run.<br>
Interval settings affect how often a snapshot is performed/retained. eg. 2 for hourly will take an "hourly" snapshot every other hour,
2 for daily will take a "daily" snapshot every other day.<br>
Retain settings affect how many of each type of snapshot to keep. eg. 24 for hours will keep the last 24 "hourly" snapshots
(not necessarily the last 24 hours if "hourly" interval is not 1). Setting the retain value for any of the types to 0 disables that one.<br>
If `--intervals` or `--retentions` are set, they will override the single `int_*` and `ret_*` arguments<br>
PRE and POST are commands that will be run before and after the snapshot, and provide a means to ensure that data is in a consistent state before
snapshotting and revert back to normal operation after snapshot has begun.<br>
Description is written as metadata to the snapshot itself and will show up in the EC2 console.

Required arguments: instance_id, --mount-point

Defaults:
* int_hour  `1`
* int_day   `1`
* int_week  `1`
* int_month `1`
* ret_hour  `24`
* ret_day   `14`
* ret_week  `4`
* ret_month `12`
* ret_year  `3`

Arguments:

      -i HOUR DAY WEEK MONTH, --intervals HOUR DAY WEEK MONTH
                            Set all intervals at once
      -r HOURS DAYS WEEKS MONTHS YEARS, --retentions HOURS DAYS WEEKS MONTHS YEARS
                            Set all retentions at once
      --int_hour HOURS      hourly interval for snapshots
      --int_day DAYS        daily interval for snapshots
      --int_week WEEKS      weekly interval for snapshots
      --int_month MONTHS    monthly interval for snapshots
      --ret_hour HOURS      number of hourly snapshots to keep
      --ret_day DAYS        number of daily snapshots to keep
      --ret_week WEEKS      number of weekly snapshots to keep
      --ret_month MONTHS    number of monthly snapshots to keep
      --ret_year YEARS      number of yearly snapshots to keep
      --pre PRE_COMMAND     command to run on host to prepare for starting EBS
                            snapshot (will not be run if volume group is not
                            attached)
      --post POST_COMMAND   command to run on host after snapshot (will not be run
                            if volume group is not attached)
      -d DESCRIPTION, --description DESCRIPTION
                            description to add to snapshot
      -m MOUNT_POINT, --mount-point MOUNT_POINT
                            mount point of the volume group to snapshot


----

#### `ams snapshot schedule add volume (volume_group_id)`
Schedule snapshots for a specific volume_group_id. Least flexible of all the schedule creations, as it will only snapshot
the volume group it is assigned to do. If the volume group is no longer in use, snapshots will continue to be created.<br>
`int_*` settings affect how often a snapshot is performed/retained. eg. 2 for hourly will take an "hourly" snapshot every other hour,
2 for daily will take a "daily" snapshot every other day.<br>
`ret_*` settings affect how many of each type of snapshot to keep. eg. 24 for hours will keep the last 24 "hourly" snapshots
(not necessarily the last 24 hours if "hourly" interval is not 1). Setting the retain value for any of the types to 0 disables that one.<br>
If `--intervals` or `--retentions` are set, they will override the single `int_*` and `ret_*` arguments<br>
PRE and POST are commands that will be run before and after the snapshot, and provide a means to ensure that data is in a consistent state before
snapshotting and revert back to normal operation after snapshot has begun.<br>
Description is written as metadata to the snapshot itself and will show up in the EC2 console.

Required arguments: volume_group_id

Defaults:
* int_hour  `1`
* int_day   `1`
* int_week  `1`
* int_month `1`
* ret_hour  `24`
* ret_day   `14`
* ret_week  `4`
* ret_month `12`
* ret_year  `3`

Arguments:

      -i HOUR DAY WEEK MONTH, --intervals HOUR DAY WEEK MONTH
                            Set all intervals at once
      -r HOURS DAYS WEEKS MONTHS YEARS, --retentions HOURS DAYS WEEKS MONTHS YEARS
                            Set all retentions at once
      --int_hour HOURS      hourly interval for snapshots
      --int_day DAYS        daily interval for snapshots
      --int_week WEEKS      weekly interval for snapshots
      --int_month MONTHS    monthly interval for snapshots
      --ret_hour HOURS      number of hourly snapshots to keep
      --ret_day DAYS        number of daily snapshots to keep
      --ret_week WEEKS      number of weekly snapshots to keep
      --ret_month MONTHS    number of monthly snapshots to keep
      --ret_year YEARS      number of yearly snapshots to keep
      --pre PRE_COMMAND     command to run on host to prepare for starting EBS
                            snapshot (will not be run if volume group is not
                            attached)
      --post POST_COMMAND   command to run on host after snapshot (will not be run
                            if volume group is not attached)
      -d DESCRIPTION, --description DESCRIPTION
                            description to add to snapshot

----

#### `ams snapshot schedule edit (schedule_id)`
Edit an existing snapshot schedule by schedule_id.<br>
`int_*` settings affect how often a snapshot is performed/retained. eg. 2 for hourly will take an "hourly" snapshot every other hour,
2 for daily will take a "daily" snapshot every other day.<br>
`ret_*` settings affect how many of each type of snapshot to keep. eg. 24 for hours will keep the last 24 "hourly" snapshots
(not necessarily the last 24 hours if "hourly" interval is not 1). Setting the retain value for any of the types to 0 disables that one.<br>
If `--intervals` or `--retentions` are set, they will override the single `int_*` and `ret_*` arguments as well as overwrite all the single
settings in the database. If you only want to update a single setting, use the single versions of the arguments<br>
PRE and POST are commands that will be run before and after the snapshot, and provide a means to ensure that data is in a consistent state before
snapshotting and revert back to normal operation after snapshot has begun.<br>
Description is written as metadata to the snapshot itself and will show up in the EC2 console. Changing the description does not update the
descriptions on snapshots that have already been created; it only changes the description for new snapshots going forward<br>
At this time, changing a snapshot schedule from volume/host/instance type to any other type is not supported. Delete the current schedule
and add a new one with different type but the same settings to achieve this functionality.


Required arguments: schedule_id

Arguments:

      -i HOUR DAY WEEK MONTH, --intervals HOUR DAY WEEK MONTH
                            Set all intervals at once
      -r HOURS DAYS WEEKS MONTHS YEARS, --retentions HOURS DAYS WEEKS MONTHS YEARS
                            Set all retentions at once
      --int_hour HOURS      hourly interval for snapshots
      --int_day DAYS        daily interval for snapshots
      --int_week WEEKS      weekly interval for snapshots
      --int_month MONTHS    monthly interval for snapshots
      --ret_hour HOURS      number of hourly snapshots to keep
      --ret_day DAYS        number of daily snapshots to keep
      --ret_week WEEKS      number of weekly snapshots to keep
      --ret_month MONTHS    number of monthly snapshots to keep
      --ret_year YEARS      number of yearly snapshots to keep
      --pre PRE_COMMAND     command to run on host to prepare for starting EBS
                            snapshot (will not be run if volume group is not
                            attached)
      --post POST_COMMAND   command to run on host after snapshot (will not be run
                            if volume group is not attached)
      -d DESCRIPTION, --description DESCRIPTION
                            description to add to snapshot


----

#### `ams snapshot schedule delete (schedule_id)`
Deletes a specific snapshot schedule. Use `ams snapshot schedule list` to find the `schedule_id` of a specific schedule

Required arguments: schedule_id

----

#### `ams snapshot schedule run [schedule_id]`
This is intended to be dropped into a cron on a single host every hour with no arguments. <br>
If a `schedule_id` is provided then the snapshot for the schedule points to will be created immediately regardless of whether it is scheduled (with a best
effort to apply the retention rules so the snapshot will eventually be cleaned up). Take note that if a valid expiry time can be calculated the
snapshot will be automatically purged per the rules of the schedule. If you want a snapshot that will not expire use `ams snapshot create` to create a snapshot.

Arguments:

      --purge      delete expired snapshots after running the schedule

----

## Networking
### Route53
#### `ams route53 discovery`
Reads the Route53 dns configurations and maps the hostnames defined in dns to the hosts in the hosts table. Currently this will pull all the records from dns down
to the database, but it only uses A and CNAME records to assign hostnames to hosts. This will not traverse recursive CNAMEs currently (or likely ever), and as a
general rule it will prefer an A record over a CNAME (I am open to arguments for/against this and any suggestions).

Arguments:

      --interactive         Enable interactive mode for applying discovered host
                            names to hosts (not enabled yet)
      --prefer {internal,external}
                            Sets which hostname gets preference if DNS records are
                            defined for an internal address and an external
                            address
      --load-only           Only load the route53 tables, but do not apply
                            hostname changes to hosts

#### `ams route53 list dns`
Lists the DNS records that are currently in the database. You can run `ams route53 discovery` to synchronize the database
with what is currently configured in Route53

Arguments:

----

#### `ams route53 list zones`
Lists the hosted zones that are currently in the database. You can run `ams route53 discovery` to synchronize the database
with what is currently configured in Route53

Arguments:

----

#### `ams route53 list healthchecks`
Lists the Route53 health checks that are currently in the database. You can run `ams route53 discovery` to synchronize the
database with what is currently configured in Route53

Arguments:

----

#### `ams route53 dns create (fqdn) (record_type)`
Create a raw DNS record in Route53. Note that currently this tool only supports single value DNS entries (ie. no support
for multiple values in a single DNS record). fqdn is the fully qualified domain name for the entry. You can include the trailing dot(.)
or it will be added automatically. record_type is the dns record type. Currently only support values `a` or `cname` for A record or
CNAME record respectively.

Required arguments: fqdn, record_type, (--zone-id | --zone-name), --record-value

Arguments:

      --zone-id ZONE_ID     Zone id to add DNS record to
      --zone-name ZONE_NAME
                            Zone name to add DNS record to
      -t TTL, --ttl TTL     TTL for the entry (default: 60)
      -r {simple,weighted,latency,failover}, --routing-policy {simple,weighted,latency,failover}
                            The routing policy to use (default: simple)
      -w WEIGHT, --weight WEIGHT
                            Weighted routing policy: weight to assign to the dns
                            resource
      --region REGION       Latency routing policy: assigns the region for the dns
                            resource for routing
      --health-check HEALTH_CHECK
                            health check id to associate with the record (for IDs,
                            use: ams route53 list healthchecks)
      --failover-role {primary,secondary}
                            Failover routing policy: defines whether resource is
                            primary or secondary
      -v RECORD_VALUE, --record-value RECORD_VALUE
                            Value for the DNS record (Currently only has support
                            single value entries)
      --identifier IDENTIFIER
                            Unique identifier to associate to a record that shares
                            a name/type with other records in weighted, latency,
                            or failover records

----

#### `ams route53 dns add (fqdn) (record_type)`
Create a DNS record for a running instance. Optionally you can also provide the parameters to create a health check for
the DNS entry. This enables easily adding records for hosts using weighted, latency, and failover DNS configurations.
fqdn is the fully qualified domain name for the entry. You can include the trailing dot(.) or it will be added automatically.
record_type is the dns record type. Currently only support values `a` or `cname` for A record or CNAME record respectively.

Required arguments: fqdn, record_type, (--zone-id | --zone-name), (--host | --instance)

Arguments:

      --zone-id ZONE_ID     Zone id to add DNS record to
      --zone-name ZONE_NAME
                            Zone name to add DNS record to
      -t TTL, --ttl TTL     TTL for the entry (default: 60)
      -r {simple,weighted,latency,failover}, --routing-policy {simple,weighted,latency,failover}
                            The routing policy to use (default: simple)
      -w WEIGHT, --weight WEIGHT
                            Weighted routing policy: weight to assign to the dns
                            resource
      --region REGION       Latency routing policy: assigns the region for the dns
                            resource for routing
      --health-check HEALTH_CHECK
                            health check id to associate with the record (for IDs,
                            use: ams route53 list healthchecks)
      --failover-role {primary,secondary}
                            Failover routing policy: defines whether resource is
                            primary or secondary
      -H HOST, --host HOST  Hostname (to find current hostname use: ams host list)
      -i INSTANCE, --instance INSTANCE
                            Instance ID
      --use {public,private}
                            Define whether to use the public or private
                            hostname/IP
      --identifier IDENTIFIER
                            Unique identifier to associate to a record that shares
                            a name/type with other records in weighted, latency,
                            or failover records. If not provided, one will be
                            created from the hostname or instance id
      --update-hosts        (routing_policy=simple only) Updates the hostname for
                            the host in the AMS hosts table (saving you from
                            having to run route53 discovery to update)
      --configure-hostname  (routing_policy=simple only) Set the hostname on the
                            host to the FQDN that was just added to the host or
                            the currently set uname (uname will override the
                            FQDN). Also applies the --update-hosts option (for
                            Ubuntu and Redhat flavors, it will also edit the
                            proper files to make this change permanent)

----

#### `ams route53 dns delete (fqdn) (record_type)`
Delete a DNS record in Route53. fqdn is the fully qualified domain name for the entry. You can include the trailing dot(.)
or it will be added automatically. record_type is the dns record type. Currently only support values `a` or `cname` for A record or
CNAME record respectively.

Required arguments: fqdn, record_type, (--zone-id | --zone-name)

Arguments:

      --identifier IDENTIFIER
                            Unique identifier for a record that shares a name/type
                            with other records in weighted, latency, or failover
                            records
      --zone-id ZONE_ID     Zone id to add DNS record to
      --zone-name ZONE_NAME
                            Zone name to add DNS record to

----

#### `ams route53 healthcheck create (ip) (port) (type)`
Creates a health check in Route53 to be able to be used for weighted, latency and failover DNS entries. ip should be a public
ip address for the host, port is the port to health check and type is one of `tcp`, `http`, `https` for their respective health check types.

Required arguments: ip, port, type

Arguments:

      -i {10,30}, --interval {10,30}
                            Health check interval (10 or 30 second)
      -f {1,2,3,4,5,6,7,8,9,10}, --failure-threshold {1,2,3,4,5,6,7,8,9,10}
                            Number of times health check fails before the host is
                            marked down by Route53
      -a RESOURCE_PATH, --resource-path RESOURCE_PATH
                            HTTP/HTTPS: health check resource path
      -d FQDN, --fqdn FQDN  HTTP/HTTPS: health check fully qualified domain name
      -s STRING_MATCH, --string-match STRING_MATCH
                            HTTP/HTTPS: health check response match string

----

## Internals
#### `ams internals database install`
This will install the database table for an initial install of AMS.

----

#### `ams internals database upgrade`
This should be run every time that the software is updated to ensure that database schema matches the application's expectation.

----
