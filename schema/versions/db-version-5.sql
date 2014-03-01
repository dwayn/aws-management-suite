ALTER TABLE snapshot_groups ADD COLUMN orig_mount_point VARCHAR(50) AFTER block_device, ADD COLUMN orig_host VARCHAR(100) AFTER orig_mount_point, ADD COLUMN orig_instance_id VARCHAR(15) AFTER orig_mount_point/* apparently snapshot schedules didn't originally have description field */;

--

UPDATE snapshot_groups JOIN host_volumes USING(volume_group_id) JOIN hosts USING(instance_id) SET snapshot_groups.orig_mount_point=host_volumes.mount_point, snapshot_groups.orig_host=hosts.host, snapshot_groups.orig_instance_id=hosts.instance_id /* set the mount points of any old snapshot groups */;