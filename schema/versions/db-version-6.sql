CREATE TABLE `deleted_volume_groups` (
  `volume_group_id` int(11) NOT NULL AUTO_INCREMENT,
  `raid_level` int(11) NOT NULL,
  `stripe_block_size` int(11) NOT NULL DEFAULT '256',
  `fs_type` varchar(30) NOT NULL,
  `block_device` varchar(30) DEFAULT NULL,
  `group_type` enum('raid','single') DEFAULT NULL,
  `tags` varchar(100) DEFAULT NULL,
  `snapshot_group_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`volume_group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--

CREATE TABLE `deleted_volumes` (
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