ALTER TABLE `ami_block_devices` MODIFY COLUMN `ami_id` VARCHAR(40) NOT NULL,
                                MODIFY COLUMN `snapshot_id` VARCHAR(40) DEFAULT NULL;

--

ALTER TABLE `amis` MODIFY COLUMN `ami_id` VARCHAR(40) NOT NULL,
                   MODIFY COLUMN `kernel_id` VARCHAR(40) DEFAULT NULL,
                   MODIFY COLUMN `ramdisk_id` VARCHAR(40) DEFAULT NULL;

--

ALTER TABLE `deleted_snapshot_groups` MODIFY COLUMN `orig_instance_id` VARCHAR(40) DEFAULT NULL;

--

ALTER TABLE `deleted_snapshots` MODIFY COLUMN `snapshot_id` VARCHAR(40) NOT NULL,
                                MODIFY COLUMN `volume_id` VARCHAR(40) DEFAULT NULL;

--

ALTER TABLE `deleted_volumes` MODIFY COLUMN `volume_id` VARCHAR(40) NOT NULL;

--

ALTER TABLE `elastic_ips` MODIFY COLUMN `instance_id` VARCHAR(40) DEFAULT NULL,
                          MODIFY COLUMN `allocation_id` VARCHAR(40) DEFAULT NULL,
                          MODIFY COLUMN `association_id` VARCHAR(40) DEFAULT NULL,
                          MODIFY COLUMN `network_interface_id` VARCHAR(40) DEFAULT NULL;

--

ALTER TABLE `host_template_sg_associations` MODIFY COLUMN `security_group_id` VARCHAR(40) NOT NULL;

--

ALTER TABLE `host_templates` MODIFY COLUMN `vpc_id` VARCHAR(40) DEFAULT NULL,
                             MODIFY COLUMN `subnet_id` VARCHAR(40) DEFAULT NULL;

--

ALTER TABLE `host_volumes` MODIFY COLUMN `instance_id` VARCHAR(40) DEFAULT NULL;

--

ALTER TABLE `hosts` MODIFY COLUMN `instance_id` VARCHAR(40) NOT NULL,
                    MODIFY COLUMN `vpc_id` VARCHAR(40) DEFAULT NULL,
                    MODIFY COLUMN `subnet_id` VARCHAR(40) DEFAULT NULL;

--

ALTER TABLE `security_group_associations` MODIFY COLUMN `security_group_id` VARCHAR(40) NOT NULL,
                                          MODIFY COLUMN `instance_id` VARCHAR(40) NOT NULL;

--

ALTER TABLE `security_group_rules` MODIFY COLUMN `security_group_id` VARCHAR(40) NOT NULL;

--

ALTER TABLE `security_groups` MODIFY COLUMN `security_group_id` VARCHAR(40) NOT NULL,
                              MODIFY COLUMN `vpc_id` VARCHAR(40)DEFAULT NULL;

--

ALTER TABLE `snapshot_groups` MODIFY COLUMN `orig_instance_id` VARCHAR(40) DEFAULT NULL;

--

ALTER TABLE `snapshot_schedules` MODIFY COLUMN `instance_id` VARCHAR(40) DEFAULT NULL;

--

ALTER TABLE `snapshots` MODIFY COLUMN `snapshot_id` VARCHAR(40) NOT NULL,
                        MODIFY COLUMN `volume_id` VARCHAR(40) NOT NULL;

--

ALTER TABLE `subnets` MODIFY COLUMN `subnet_id` VARCHAR(40) NOT NULL;

--

ALTER TABLE `volumes` MODIFY COLUMN `volume_id` VARCHAR(40) NOT NULL;

--

ALTER TABLE `vpcs` MODIFY COLUMN `vpc_id` VARCHAR(40) NOT NULL;
