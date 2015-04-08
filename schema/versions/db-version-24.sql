CREATE TABLE `vpcs` (
  `vpc_id` VARCHAR (32) NOT NULL,
  `region` VARCHAR (20) NOT NULL,
  `cidr` VARCHAR (20),
  `is_default` TINYINT (1),
  `start_inet` INT (11) UNSIGNED,
  `end_inet` INT (11) UNSIGNED,
  `active` TINYINT (1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`vpc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--

CREATE TABLE `subnets` (
  `subnet_id` VARCHAR (32) NOT NULL,
  `vpc_id` VARCHAR (32) NOT NULL,
  `availability_zone` VARCHAR (20) NOT NULL,
  `cidr` VARCHAR (20),
  `start_inet` INT (11) UNSIGNED,
  `end_inet` INT (11) UNSIGNED,
  `active` TINYINT (1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`subnet_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;