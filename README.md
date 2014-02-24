aws-management-suite
====================


# Introduction
This is currently very much a work in progress, and there is much that will be cleaned up over time. The goal of this suite is to
abstract many of the common tasks related to managing cloud infrastructure in AWS.

## Current Features
SSH client
* password or private key based login
* support for sudo login (password or passwordless)
* captures stdout, stderr and exit code from command run
EBS Volumes (managed as groups of volumes)
* create volumes
* attach volumes
* create software raid
* assemble software raid
* mount volume/raid
EBS Snapshots (managed as groups of snapshots)
* pre/post snapshot hooks to enable running commands/scripts on target host before and after starting snapshot to ensure consistent point in time snapshot of all volumes in a raid group
* copy snapshot group
* clone snapshot group to new volume group
  * clone latest snapshot of a volume group or host/instance + mount point
Instance Management
* Currently instances need to be added to the hosts table manually, there is a feature planned to add a discovery script so that many of these things can be automatically populated

## Setup and Configuration
### Initial installation
* Copy sample_settings.py to settings.py and edit AWS, SSH and SUDO access credentials
* A MySQL database needs to be setup for tracking state. The following statements assume that the mysql database and the tool are located on the same host:
 * `CREATE DATABASE ams;` -- Create the schema
 * `GRANT ALL PRIVILEGES ON ams.* TO 'ams_user'@'localhost' IDENTIFIED BY 'mypass';` -- (This will create user with username 'ams_user' and password of 'mypass' and give access to the new schema created)
* Edit TRACKING_DB credentials in settings.py with the proper credentials for your MySQL database
* `pip install -r requirements.txt` will install the handful of external dependencies
* Suggested: add the path to ams directory to your path or add symlink to `ams` script to a directory in the system path
* `ams internals database install` will create the current full version of all of the tables

### Upgrading
If you have updated the code base, just run `ams internals database upgrade` to run the update scripts. Upgrade can be run as often as you like, as it will do nothing if the database version matches the code version.



# Management Tool Usage

## General
All of the functionality is through the command line tool `ams`. It has been implemented as a multi-level nested command parser using the argparse module.<br>
If at any point you need help just add `-h` or `--help` flag to the command line and it will list all available sub-commands and options for the current command.<br>
There are still a few legacy command structures that need to be cleaned up, so there may be some minor changes to the syntax to a few of these, but I will attempt to keep these to an absolute minimum.


## Host/Instance
### `ams host list`
With no options this lists all host entries in the database

    optional arguments:
      --like LIKE         string to find within 'search-field'
      --prefix PREFIX     string to prefix match against 'search-field'
      --zone ZONE         Availability zone to filter results by. This is a prefix
                          search so any of the following is valid with increasing
                          specificity: 'us', 'us-west', 'us-west-2', 'us-west-2a'

----

#### `ams host list host [hostname]`
If `hostname` is given then it will match hostname exactly

    optional arguments:
      --like LIKE         wildcard matches hostname
      --prefix PREFIX     prefix matches hostname
      --zone ZONE         Availability zone to filter results by. This is a prefix
                          search so any of the following is valid with increasing
                          specificity: 'us', 'us-west', 'us-west-2', 'us-west-2a'


----

#### `ams host list instance_id [instance id]`
If `instance id` is given then it will match instance_id exactly

    optional arguments:
      --like LIKE         wildcard matches instance id
      --prefix PREFIX     prefix matches instance id
      --zone ZONE         Availability zone to filter results by. This is a prefix
                          search so any of the following is valid with increasing
                          specificity: 'us', 'us-west', 'us-west-2', 'us-west-2a'

----

## Volumes



## Snapshots

## Internals


