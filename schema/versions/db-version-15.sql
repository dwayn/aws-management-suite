ALTER TABLE `hosts` ADD COLUMN `vpc_id` varchar(32) DEFAULT NULL AFTER `uname`;

--

ALTER TABLE `hosts` ADD COLUMN `subnet_id` varchar(32) DEFAULT NULL AFTER `vpc_id`;