CREATE TABLE `tags` (
  `resource_id` VARCHAR(64) NOT NULL,
  `name` VARCHAR(127) NOT NULL,
  `value` VARCHAR(255) NOT NULL DEFAULT '',
  `removed` TINYINT(1) NOT NULL DEFAULT 0,
  `type` ENUM ('standard', 'extended') NOT NULL DEFAULT 'standard',
  PRIMARY KEY (`resource_id`, `name`),
  KEY `idx_name_value_resourceid` (`name`, `value`, `resource_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;