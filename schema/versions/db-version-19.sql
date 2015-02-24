CREATE TABLE `availability_zones` (
  `availability_zone` VARCHAR(20) NOT NULL,
  `region` VARCHAR(20) NOT NULL,
  `active` TINYINT (1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`availability_zone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;