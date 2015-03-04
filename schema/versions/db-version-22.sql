CREATE TABLE `elastic_ips` (
  `public_ip` VARCHAR (15) NOT NULL,
  `region` VARCHAR (20) NOT NULL,
  `instance_id` VARCHAR (15) DEFAULT NULL,
  `domain` ENUM('standard', 'vpc') NOT NULL ,
  `allocation_id` VARCHAR(20) DEFAULT NULL,
  `association_id` VARCHAR(20) DEFAULT NULL,
  `network_interface_id` VARCHAR(20) DEFAULT NULL,
  `private_ip` VARCHAR(15) DEFAULT NULL,
  `active` TINYINT (1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`public_ip`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
