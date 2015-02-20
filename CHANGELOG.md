aws-management-suite Change Log
===============================

### February 19, 2015

* Dynamic inventory generation for easy integration of AMS with Ansible's [(Dynamic Inventory)](http://docs.ansible.com/intro_dynamic_inventory.html)
 * ams-inventory script can now be used as the inventory argument for ansible using `ansible -i /path/to/ams/ams-inventory` to use the AMS database to dynamically configure an ansible installation 
 * Management of server group hierarchies supported using `ams-inventory` script
 * Templates can be applied to host tags to assign hosts to ansible groups dynamically
 * Management of tag templates handled through `ams-inventory` script


### February 13, 2015

* Added tag management support for instances
 * Tags can be added or removed on instances or groups of instances (filtering can be done on tags to determine what instance to apply tag changes to)
 * AMS supports extended tagging of AWS resources, allowing you to add more than 10 tags to a resource
  * Currently you are required to explicitly choose extended type for a tag, but I am considering making the tag type automatically change to extended for new tags when the AWS limit is reached for that resource (currently it will have an error and fail to add the tag) 
 * Soon to come: support for filtering by tags in other `ams host *` commands


### February 12, 2015

* Rewrote the app config to move default configs into the database, and config files are now in ini format
 * Legacy settings.py is now deprecated and issue a warning if the configuration is loaded from settings.py
 * Soon to come: management of the configs in the database from the command line tools
* Database install now uses the same code path as database upgrade, so database install starts at version 0 and applies each of the database upgrade scripts in order
 * This will ensure that database install and upgrade no longer get out of sync with each other



### January 29, 2015

* Added collection and storing of VPC ID and Subnet ID for instances  
* Refactored all of the ssh calls to use internal IP address for VPC instances and external EC2 DNS for EC2 Classic instances
 * This has an added benefit of not requiring hostname to be set for an instance in order to be able to ssh to them




### Previous changes not logged
