ALTER TABLE volume_groups ADD COLUMN snapshot_group_id int(11)/* for a volume group that was created from a snapshot group */;

--

ALTER TABLE snapshots ADD COLUMN description varchar(255)/* need to store the descriptions on snapshots so that they can persist on copy */;

--

ALTER TABLE host_volumes DROP PRIMARY KEY, DROP KEY volume_group_id, ADD PRIMARY KEY(volume_group_id), ADD UNIQUE KEY instance_id_mount_point(instance_id, mount_point)/* changing the keys on the host volumes table to enforce proper uniqueness */;