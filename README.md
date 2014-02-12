aws-management-suite
====================


# Introduction
This is currently very much a work in progress, and there is much that will be cleaned up over time. The goal of this suite is to
abstract many of the common tasks related to managing cloud infrastructure in AWS.

## Current Features
* SSH client
 * password or private key based login
 * support for sudo login (password or passwordless)
 * captures stdout, stderr and exit code from command run
* EBS Volumes (managed as groups of volumes)
 * create volumes
 * attach volumes
 * create software raid
 * assemble software raid
 * mount volume/raid
* EBS Snapshots (managed as groups of snapshots)
 * pre/post snapshot hooks to enable running commands/scripts on target host before and after starting snapshot to ensure consistent point in time snapshot of all volumes in a raid group
 *
* Instance Management
 * Currently instances need to be added to the hosts table manually, there is a feature planned to add a discovery script so that many of these things can be automatically populated

## Setup and Configuration
* Copy sample_settings.py to settings.py and edit AWS, SSH and SUDO access credentials
* A MySQL database needs to be setup for tracking state. Load the schema.sql file to initialize the schema.
* Edit TRACKING_DB credentials in settings.py with the proper credentials for your MySQL database



