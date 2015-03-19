CREATE TABLE `amis` (
  `ami_id` VARCHAR (20) NOT NULL,
  `region` VARCHAR (20) NOT NULL,
  `name` VARCHAR (255) DEFAULT NULL,
  `description` VARCHAR (255) DEFAULT NULL,
  `location` VARCHAR (512) NOT NULL,
  `state` VARCHAR (25) NOT NULL,
  `owner_id` BIGINT (20) NOT NULL,
  `owner_alias` VARCHAR (127) DEFAULT NULL,
  `is_public` TINYINT (1) NOT NULL,
  `architecture` VARCHAR (32) DEFAULT NULL,
  `platform` VARCHAR (127) DEFAULT NULL,
  `type` VARCHAR (32) DEFAULT NULL,
  `kernel_id` VARCHAR (20) DEFAULT NULL,
  `ramdisk_id` VARCHAR (20) DEFAULT NULL,
  `product_codes` TEXT DEFAULT NULL,
  `billing_products` TEXT DEFAULT NULL,
  `root_device_type` VARCHAR (16) NOT NULL,
  `root_device_name` VARCHAR (64) NOT NULL,
  `virtualization_type` ENUM ('hvm', 'paravirtual') NOT NULL,
  `hypervisor` ENUM ('ovm','xen') NOT NULL,
  `sriov_net_support` VARCHAR(16) DEFAULT NULL,
  `active` TINYINT (1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`ami_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--

CREATE TABLE `ami_block_devices` (
  `ami_id` VARCHAR (20) NOT NULL,
  `device_name` VARCHAR (64) NOT NULL,
  `ephemeral_name` VARCHAR (64) DEFAULT NULL,
  `snapshot_id` VARCHAR (20) DEFAULT NULL,
  `delete_on_termination` TINYINT (1) NOT NULL DEFAULT 0,
  `size` INT (11),
  `volume_type` VARCHAR (16),
  `iops` INT (11) DEFAULT NULL,
  `encrypted` TINYINT (1),
  `active` TINYINT (1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`ami_id`, `device_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;