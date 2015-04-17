CREATE TABLE `host_templates` (
  `template_id` INT(11) NOT NULL AUTO_INCREMENT,
  `template_name` VARCHAR(32) NOT NULL,
  `region` VARCHAR(20),
  `instance_type` VARCHAR(15),
  `ami_id` VARCHAR(100),
  `key_name` VARCHAR(255),
  `zone` VARCHAR(20),
  `monitoring` TINYINT(1),
  `vpc_id` varchar(32),
  `subnet_id` varchar(32),
  `private_ip` varchar(20),
  `ebs_optimized` TINYINT(1),
  `name` VARCHAR(255),
  PRIMARY KEY (`template_id`),
  UNIQUE KEY ix_name(`template_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--

CREATE TABLE `host_template_sg_associations` (
  `template_id` INT(11) NOT NULL,
  `security_group_id` VARCHAR(20) NOT NULL,
  PRIMARY KEY (`template_id`, `security_group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--

CREATE TABLE `host_template_tags` (
  `template_id` INT(11) NOT NULL,
  `name` VARCHAR(127) NOT NULL,
  `value` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`template_id`, `name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;