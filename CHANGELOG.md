aws-management-suite Change Log
===============================

### April 21, 2015
* Added support for controlling instance state using `ams host control`
* Fixed a few small bugs related to template management and host creation using templates

### April 17, 2015
* Added host creation templates and tools to manage templates
 * `ams host template list` list available templates
 * `ams host template create` create new templates
 * `ams host template edit` edit existing templates
 * `ams host template delete` delete templates
 * `ams host create` now accepts a template id or template name to use as a basis for host creation, and contextual autocomplete updated to include template data into contexts   

### April 15, 2015
* Added support for creating instances using `ams host create`
 * added more contextual support for completions so that completions get filtered better based on options already provided 

### April 13, 2015
* Added cli commands to manage the application configuration that is stored in the database
 * `ams internals config list`
 * `ams internals config update`

### April 8, 2015
* Added collection of VPC and VPC subnet information in `ams vpc discovery`
* Added `ams vpc list` command to list information about VPCs and subnets
* Added functionality to a number of autocomplete functions to make completions use contextual information from other command line arguments that have already been provided to filter the completion set

### March 18, 2015
* Added collection of AMI information to host discovery
 * Added `ams host ami list` command to list available AMIs

### March 3, 2015
* Added collection of Security Group information to network discovery
 * Added `ams network security_groups list` command to list available security groups
* Added collection allocated elastic IP addresses to network discovery
 * Added `ams network elastic_ips list` command to list elastic IP addresses
* Added collection ssh keypair data in host discovery
 * Added `ams host keys list` command  to list the available key pairs

### Februrary 26, 2015
* Added new module network accessible via `ams network`
 * Added discovery for security groups
 * Added list functionality for security groups
* Added module for argcomplete to start adding functions so that bash completion also includes values from the database in its completions
 * Database value completion implemented for `ams network`
* Host discovery now also loads all AWS regions and availability zones into the AMS database

### February 20, 2015
* Removed the monkey patches for boto libraries related to Route53 healthchecks and failover records
* Increased the minimum required version of boto to 2.36.0
* Added functionality to Config to force upgrade of boto module if needed

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
