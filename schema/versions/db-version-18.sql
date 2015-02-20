CREATE TABLE `inventory_groups` (
  `inventory_group_id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(127) NOT NULL,
  PRIMARY KEY (`inventory_group_id`),
  UNIQUE KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--

CREATE TABLE `inventory_group_map` (
  `parent_id` int(11) NOT NULL,
  `child_id` int(11) NOT NULL,
  PRIMARY KEY (`parent_id`,`child_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--

CREATE TABLE `inventory_group_templates` (
  `inventory_group_template_id` int(11) NOT NULL AUTO_INCREMENT,
  `template` varchar(255) NOT NULL,
  PRIMARY KEY (`inventory_group_template_id`),
  UNIQUE KEY `idx_template` (`template`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--

ALTER TABLE `tags` CHANGE `type` `type` enum('standard','extended', 'hostvar') NOT NULL DEFAULT 'standard';