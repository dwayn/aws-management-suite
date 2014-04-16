ALTER TABLE `route53_records` ADD COLUMN `healthcheck_id` VARCHAR (50) DEFAULT NULL AFTER `region`;

--

CREATE TABLE `route53_healthchecks` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `healthcheck_id` varchar(50) NOT NULL,
  `ip` varchar(20) NOT NULL,
  `port` int(11) NOT NULL,
  `type` varchar(15) NOT NULL,
  `request_interval` int(11) NOT NULL,
  `failure_threshold` int(11) NOT NULL,
  `resource_path` varchar(255) DEFAULT NULL,
  `search_string` varchar(255) DEFAULT NULL,
  `fqdn` varchar(255) DEFAULT NULL,
  `caller_reference` varchar(50) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `healthcheck_id` (`healthcheck_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8