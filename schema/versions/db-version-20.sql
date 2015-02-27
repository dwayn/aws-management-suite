CREATE TABLE `security_groups` (
  `security_group_id` VARCHAR(20) NOT NULL,
  `region` VARCHAR (20) NOT NULL,
  `name` VARCHAR (255),
  `description` VARCHAR (255),
  `vpc_id` VARCHAR(32),
  `active` TINYINT (1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`security_group_id`),
  INDEX `ix_region` (`region`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--

CREATE TABLE `security_group_associations` (
  `security_group_id` VARCHAR(20) NOT NULL,
  `instance_id` VARCHAR (15) NOT NULL,
  `active` TINYINT (1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`security_group_id`, `instance_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--

CREATE TABLE `security_group_rules` (
  `security_group_id` VARCHAR(20) NOT NULL,
  `type` ENUM ('ingress', 'egress') NOT NULL,
  `protocol` VARCHAR (15) NOT NULL,
  `from_port` INTEGER (11)NOT NULL,
  `to_port` INTEGER (11) NOT NULL,
  `grants` TEXT NOT NULL ,
  `active` TINYINT (1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`security_group_id`, `type`, `protocol`, `from_port`, `to_port`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;