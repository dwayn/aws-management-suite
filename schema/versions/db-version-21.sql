CREATE TABLE `key_pairs` (
  `region` VARCHAR (20) NOT NULL,
  `key_name` VARCHAR (255) NOT NULL,
  `fingerprint` VARCHAR (127) DEFAULT NULL,
  `active` TINYINT (1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`region`,`key_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--

ALTER TABLE `hosts` ADD COLUMN `key_name` VARCHAR (255) AFTER `subnet_id`;