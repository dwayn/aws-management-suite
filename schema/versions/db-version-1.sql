CREATE TABLE `host_volumes` (
  `instance_id` varchar(15) NOT NULL,
  `volume_group_id` int(11) NOT NULL,
  `mount_point` varchar(50) DEFAULT NULL,
  `notes` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`instance_id`,`volume_group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `hosts` (
  `instance_id` varchar(15) NOT NULL,
  `host` varchar(100) DEFAULT NULL,
  `hostname_internal` varchar(100) DEFAULT NULL,
  `hostname_external` varchar(100) DEFAULT NULL,
  `ip_internal` varchar(15) DEFAULT NULL,
  `ip_external` varchar(15) DEFAULT NULL,
  `ami_id` varchar(100) DEFAULT NULL,
  `instance_type` varchar(15) DEFAULT NULL,
  `availability_zone` varchar(20) DEFAULT NULL,
  `tags` varchar(100) DEFAULT NULL,
  `notes` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`instance_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `snapshot_groups` (
  `snapshot_group_id` int(11) NOT NULL AUTO_INCREMENT,
  `volume_group_id` int(11) NOT NULL,
  `raid_level` int(11) DEFAULT NULL,
  `stripe_block_size` int(11) NOT NULL,
  `fs_type` varchar(30) NOT NULL,
  `block_device` varchar(30) DEFAULT NULL,
  `group_type` enum('raid','single') DEFAULT NULL,
  `tags` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`snapshot_group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `snapshots` (
  `snapshot_id` varchar(20) NOT NULL,
  `snapshot_group_id` int(11) NOT NULL,
  `volume_id` varchar(15) NOT NULL,
  `size` int(11) NOT NULL,
  `piops` int(11) DEFAULT NULL,
  `block_device` varchar(30) DEFAULT NULL,
  `raid_device_id` int(11) NOT NULL,
  `created_date` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `expiry_date` datetime DEFAULT NULL,
  `region` varchar(20) DEFAULT NULL,
  `tags` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`snapshot_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `volume_groups` (
  `volume_group_id` int(11) NOT NULL AUTO_INCREMENT,
  `raid_level` int(11) NOT NULL,
  `stripe_block_size` int(11) NOT NULL DEFAULT '256',
  `fs_type` varchar(30) NOT NULL,
  `block_device` varchar(30) DEFAULT NULL,
  `group_type` enum('raid','single') DEFAULT NULL,
  `tags` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`volume_group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `volumes` (
  `volume_id` varchar(15) NOT NULL,
  `volume_group_id` int(11) NOT NULL,
  `availability_zone` varchar(20) NOT NULL,
  `size` int(11) NOT NULL,
  `piops` int(11) DEFAULT NULL,
  `block_device` varchar(30) DEFAULT NULL,
  `raid_device_id` int(11) NOT NULL,
  `tags` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`volume_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `snapshot_schedules` (
  `schedule_id` int(11) NOT NULL AUTO_INCREMENT,
  `hostname` varchar(100) DEFAULT NULL,
  `instance_id` varchar(15) DEFAULT NULL,
  `block_device` varchar(30) DEFAULT NULL,
  `mount_point` varchar(50) DEFAULT NULL,
  `volume_group_id` int(11) DEFAULT NULL,
  `interval_hour` int(11) NOT NULL DEFAULT '1',
  `interval_day` int(11) NOT NULL DEFAULT '1',
  `interval_week` int(11) NOT NULL DEFAULT '1',
  `interval_month` int(11) NOT NULL DEFAULT '1',
  `retain_hourly` int(11) NOT NULL DEFAULT '24',
  `retain_daily` int(11) NOT NULL DEFAULT '14',
  `retain_weekly` int(11) NOT NULL DEFAULT '4',
  `retain_monthly` int(11) NOT NULL DEFAULT '12',
  `retain_yearly` int(11) NOT NULL DEFAULT '3',
  `pre_command` varchar(256) DEFAULT NULL,
  `post_command` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`schedule_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `config` (
  `var` varchar(50) NOT NULL,
  `value` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`var`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;