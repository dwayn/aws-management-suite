aws-management-suite Change Log
===============================

### February 12, 2015

* Rewrote the app config to move default configs into the database, and config files are now in ini format
 * Legacy settings.py is now deprecated and issue a warning if the configuration is loaded from settings.py
 * Soon to come: management of the configs in the database from the command line tools
* Database install now uses the same code path as database upgrade, so database install starts at version 0 and applies each of the database upgrade scripts
 * This will ensure that database install and upgrade no longer get out of sync with each other



### January 29, 2015

* Added collection and storing of VPC ID and Subnet ID for instances  
* Refactored all of the ssh calls to use internal IP address for VPC instances and external EC2 DNS for EC2 Classic instances
 * This has an added benefit of not requiring hostname to be set for an instance in order to be able to ssh to them




### Previous changes not logged
