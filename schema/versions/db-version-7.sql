CREATE TABLE `deleted_snapshot_groups` (
  `snapshot_group_id` int(11) NOT NULL AUTO_INCREMENT,
  `volume_group_id` int(11) NOT NULL,
  `raid_level` int(11) DEFAULT NULL,
  `stripe_block_size` int(11) NOT NULL,
  `fs_type` varchar(30) NOT NULL,
  `block_device` varchar(30) DEFAULT NULL,
  `orig_mount_point` varchar(50) DEFAULT NULL,
  `orig_instance_id` varchar(15) DEFAULT NULL,
  `orig_host` varchar(100) DEFAULT NULL,
  `group_type` enum('raid','single') DEFAULT NULL,
  `tags` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`snapshot_group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--

CREATE TABLE `deleted_snapshots` (
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
  `description` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`snapshot_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;