ALTER TABLE `config`
MODIFY COLUMN `var` VARCHAR (64) NOT NULL,
ADD COLUMN `type` ENUM('int', 'string', 'bool', 'path') NOT NULL DEFAULT 'string',
ADD COLUMN `env_overrides` VARCHAR(255) DEFAULT NULL,
ADD COLUMN `description` VARCHAR(1024) DEFAULT NULL,
ADD COLUMN `configurable` TINYINT(1) NOT NULL DEFAULT 1;

--

INSERT INTO `config` (`var`, `value`, `type`, `env_overrides`, `description`) VALUES
  ('AWS_ACCESS_KEY', NULL, 'string', 'AMS_AWS_ACCESS_KEY,AWS_ACCESS_KEY', 'AWS Access Key String'),
  ('AWS_SECRET_KEY', NULL, 'string', 'AMS_AWS_SECRET_KEY,AWS_SECRET_KEY', 'AWS Secret Key String'),
  ('SSH_USER', 'root', 'string', 'AMS_SSH_USER', 'User that AMS uses to ssh to hosts'),
  ('SSH_PORT', '22', 'int', 'AMS_SSH_PORT', 'Port to ssh to on hosts'),
  ('SSH_PASSWORD', NULL, 'string', 'AMS_SSH_PASSWORD', 'Password for ssh user'),
  ('SSH_KEYFILE', '~/.ssh/id_rsa', 'path', 'AMS_SSH_KEYFILE', 'Path to private key to use for ssh to hosts'),
  ('SUDO_PASSWORD', NULL, 'string', 'AMS_SUDO_PASSWORD', 'Sudo password for the ssh user'),
  ('FREEZE_FILESYSTEM', '0', 'bool', 'AMS_FREEZE_FILESYSTEM', 'Set this to True to, by default, run fsfreeze to freeze/unfreeze the filesystem for a volume when snapshotting'),
  ('AMS_LOGLEVEL', 'INFO', 'string', NULL, 'Sets the output log level of AMS libraries, supported values: DEBUG, INFO, WARNING, ERROR, CRITICAL'),
  ('GLOBAL_LOGLEVEL', 'CRITICAL', 'string', NULL, 'Sets the output log level of all other modules, supported values: DEBUG, INFO, WARNING, ERROR, CRITICAL'),
  ('THROW_ERRORS', '0', 'bool', NULL, 'Rethrows globally caught errors rather than just logging a critical error'),
  ('HUMAN_OUTPUT', '1', 'bool', 'AMS_HUMAN_MODE', 'Formats output in a more human readable format by default'),
  ('ENABLE_LEGACY_CONFIG', '1', 'bool', NULL, 'Enables parsing of the legacy setting.py configs'),
  ('TRACKING_DB.host', NULL, 'string', 'AMS_DB_HOST', 'Environment variable to set Mysql host'),
  ('TRACKING_DB.port', NULL, 'string', 'AMS_DB_PORT', 'Environment variable to set Mysql port'),
  ('TRACKING_DB.user', NULL, 'string', 'AMS_DB_USER', 'Environment variable to set Mysql user'),
  ('TRACKING_DB.pass', NULL, 'string', 'AMS_DB_PASSWORD', 'Environment variable to set Mysql password'),
  ('TRACKING_DB.dbname', NULL, 'string', 'AMS_DB_NAME', 'Environment variable to set Mysql dbname');

--

UPDATE `config` SET `type`='int', `description`='Current version of the internal database tables', `configurable`=0 WHERE `var`='DATABASE_VERSION';

--

UPDATE `config` SET `configurable`=0 WHERE `var` LIKE 'TRACKING_DB%';