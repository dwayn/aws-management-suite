ALTER TABLE `ami_block_devices` MODIFY COLUMN `snapshot_id` VARCHAR(25) DEFAULT NULL;

--

ALTER TABLE `deleted_snapshots` MODIFY COLUMN `snapshot_id` VARCHAR(25) NOT NULL;

--

ALTER TABLE `deleted_snapshots` MODIFY COLUMN `volume_id` VARCHAR(25) DEFAULT NULL;

--

ALTER TABLE `deleted_volumes` MODIFY COLUMN `volume_id` VARCHAR(25) DEFAULT NULL;

--

ALTER TABLE `elastic_ips` MODIFY COLUMN `instance_id` VARCHAR(25) DEFAULT NULL;

--

ALTER TABLE `host_volumes` MODIFY COLUMN `instance_id` VARCHAR(25) DEFAULT NULL;

--

ALTER TABLE `hosts` MODIFY COLUMN `instance_id` VARCHAR(25) DEFAULT NULL;

--

ALTER TABLE `security_group_associations` MODIFY COLUMN `instance_id` VARCHAR(25) DEFAULT NULL;

--

ALTER TABLE `snapshot_schedules` MODIFY COLUMN `instance_id` VARCHAR(25) DEFAULT NULL;

--

ALTER TABLE `snapshots` MODIFY COLUMN `snapshot_id` VARCHAR(25) DEFAULT NULL;

--

ALTER TABLE `volumes` MODIFY COLUMN `volume_id` VARCHAR(25) DEFAULT NULL;