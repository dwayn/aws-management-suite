ALTER TABLE host_volumes ADD UNIQUE KEY(volume_group_id)  /* ensure volume_group_id can't end up in state where it appears attached to more than one host */;
