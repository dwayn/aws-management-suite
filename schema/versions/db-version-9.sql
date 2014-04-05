update volumes set block_device = replace(block_device, '/dev/sd', '/dev/xvd') where block_device like '/dev/sd%';

--

update volume_groups set block_device = replace(block_device, '/dev/sd', '/dev/xvd') where block_device like '/dev/sd%';

--

update snapshots set block_device = replace(block_device, '/dev/sd', '/dev/xvd') where block_device like '/dev/sd%';

--

update snapshot_groups set block_device = replace(block_device, '/dev/sd', '/dev/xvd') where block_device like '/dev/sd%';

--

update deleted_volumes set block_device = replace(block_device, '/dev/sd', '/dev/xvd') where block_device like '/dev/sd%';

--

update deleted_volume_groups set block_device = replace(block_device, '/dev/sd', '/dev/xvd') where block_device like '/dev/sd%';

--

update deleted_snapshots set block_device = replace(block_device, '/dev/sd', '/dev/xvd') where block_device like '/dev/sd%';

--

update deleted_snapshot_groups set block_device = replace(block_device, '/dev/sd', '/dev/xvd') where block_device like '/dev/sd%';
