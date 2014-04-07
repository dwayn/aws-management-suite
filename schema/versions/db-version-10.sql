CREATE TABLE `route53_zones` (
  `zone_id` varchar(50) NOT NULL,
  `name` varchar(255) NOT NULL ,
  `record_sets` INT NOT NULL DEFAULT 0,
  `comment` VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`zone_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--

CREATE TABLE `route53_records` (
  `zone_id` varchar(50) NOT NULL,
  `name` varchar(255) NOT NULL,
  `type` VARCHAR(20) NOT NULL,
  `identifier` VARCHAR(255) NOT NULL DEFAULT "",
  `resource_records` TEXT NOT NULL,
  `ttl` INT DEFAULT NULL,
  `alias_hosted_zone_id` VARCHAR(50) DEFAULT NULL,
  `alias_dns_name` VARCHAR(255) DEFAULT NULL,
  `weight` INT DEFAULT NULL,
  `region` VARCHAR(20) DEFAULT NULL,
  PRIMARY KEY (`zone_id`, `name`, `type`, `identifier`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;