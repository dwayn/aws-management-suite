__author__ = 'dwayn'

import os

def env(keys, dflt):
    if isinstance(keys, basestring):
        keys = [ keys ]
    for key in keys:
        if os.environ.has_key(key):
            return os.environ.get(key)
    return dflt

# All settings can be set via the environment or explicitly within this file.  To give a setting the Python
# value of None via an environment variable, assign it the string 'None'

# The AWS credentials may be supplied as environment variables with either the standard AWS
# naming convention or with AWSMS-specific environment variable names
AWS_ACCESS_KEY = env(['AWSMS_AWS_ACCESS_KEY', 'AWS_ACCESS_KEY'], 'some_aws_access_key')
AWS_SECRET_KEY = env(['AWSMS_AWS_SECRET_KEY', 'AWS_SECRET_KEY'], 'some_aws_secret_key')

SSH_USER =       env('AWSMS_SSH_USER',         'some_user')
SSH_PORT =       env('AWSMS_SSH_PORT',         22)
# the credential settings for ssh/sudo below can be a string or None
SSH_PASSWORD =   env('AWSMS_SSH_PASSWORD',    'some_password')
SSH_KEYFILE =    env('AWSMS_SSH_KEYFILE',     '~/.ssh/id_rsa.pub')
SUDO_PASSWORD =  env('AWSMS_SUDO_PASSWORD',   'some_sudo_password')

TRACKING_DB = {
    'host'   :  env('AWSMS_DB_HOST',          'localhost'),
    'port'   :  env('AWSMS_DB_PORT',          3306),
    'user'   :  env('AWSMS_DB_USER',          'ams_user'),
    'pass'   :  env('AWSMS_DB_PASSWORD',      'some_db_password'),
    'dbname' :  env('AWSMS_DB_NAME',          'ams'),
}

# Turn the string "None" into None in password fields
SSH_PASSWORD = None if not SSH_PASSWORD or SSH_PASSWORD.lower() == 'none' else SSH_PASSWORD
SUDO_PASSWORD = None if not SUDO_PASSWORD or SUDO_PASSWORD.lower() == 'none' else SUDO_PASSWORD

# Set this to True to, by default, run fsfreeze to freeze/unfreeze the filesystem for a volume when snapshotting
FREEZE_FILESYSTEM = env('AWSMS_FREEZE_FILESYSTEM', False)

# Expand '~' if it has been used to specify the ssh keyfile location
SSH_KEYFILE = None if not SSH_KEYFILE else os.path.expanduser(SSH_KEYFILE)
# sets the output log level, supported values: DEBUG, INFO, WARNING, ERROR, CRITICAL
AMS_LOGLEVEL = 'INFO'
# set the log level for all modules using logging module
GLOBAL_LOGLEVEL = 'CRITICAL'

# rethrows globally caught error rather than just logging a critical error
THROW_ERRORS = False