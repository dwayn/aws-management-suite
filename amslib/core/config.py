import MySQLdb
import argparse
import prettytable
import logging
import os
import ConfigParser
from errors import *
import pprint
import _mysql_exceptions

class Config:

    def __init__(self):
        self.NEED_INSTALL = False
        self.NEED_UPGRADE = False
        self.DISABLE_OPERATIONS = False
        self.DATABASE_VERSION = 0
        self._logger = self.get_logger()

        self._iniconfigs = {}
        self._dbconfigs = {}
        self._legacyConfigs = {}
        self._sources = {}
        self._env_overrides = {}
        self._inifile = None

        self.load_legacy()
        self.load_ini()
        self.load_database()

        self.combine()
        if self.NEED_INSTALL or self.NEED_UPGRADE:
            self.DISABLE_OPERATIONS = True


    def load_database(self):
        dbconn = MySQLdb.connect(host=self.TRACKING_DB['host'],
                             port=self.TRACKING_DB['port'],
                             user=self.TRACKING_DB['user'],
                             passwd=self.TRACKING_DB['pass'],
                             db=self.TRACKING_DB['dbname'])
        db = dbconn.cursor()
        try:
            db.execute("select var, value, type, env_overrides from config")
            rows = db.fetchall()
            if not rows:
                self._logger.warn("Database has not been installed, before continuing you must run: ams internals database install")
                self.NEED_INSTALL = True
                return
            for row in rows:
                name, value, vartype, env_overrides = row
                if str(name).startswith('TRACKING_DB'):
                    continue
                if value is not None:
                    if vartype == 'int':
                        value = int(value)
                    if vartype == 'string':
                        value = str(value)
                    elif vartype == 'bool':
                        value = bool(value)
                    elif vartype == 'path':
                        value = os.path.realpath(os.path.expanduser(value))

                self._dbconfigs[str(name)] = value
                if env_overrides:
                    self._env_overrides[str(name)] = self.env(str(env_overrides).split(','), None)




        except _mysql_exceptions.ProgrammingError as e:
            if e.args[0] == 1146:
                self.NEED_INSTALL = True
                self._logger.warn("Database has not been installed, before continuing you must run: ams internals database install")
                return

        except _mysql_exceptions.OperationalError as e:
            if e.args[0] == 1054:
                self.NEED_UPGRADE = True
                self._logger.warn("Database needs to be updated, before continuing you must run: ams internals database upgrade")
                return


        pass


    def load_legacy(self):
        import settings
        for k in dir(settings):
            if k.startswith('__') or k == 'os' or k == 'env':
                continue
            name = k
            if name == 'human_output':
                name = name.upper()
            self._legacyConfigs[name] = getattr(settings, k)



    def load_ini(self):
        config_file_paths = [
            '~/ams.ini',
            '/etc/ams.ini',
            os.path.realpath(os.path.dirname(__file__)+'/../../defaults.ini'),
        ]

        filename = None
        for filepath in config_file_paths:
            filename = os.path.realpath(os.path.expanduser(filepath))
            if os.path.isfile(filename):
                break
            else:
                filename = None

        if not filename:
            raise NoConfigFile("No config file found in "+" or ".join(config_file_paths))

        self._inifile = filename
        config = ConfigParser.ConfigParser()
        config.optionxform = str
        config.read(filename)
        TRACKING_DB = {}
        self._using_legacy = False
        if 'TRACKING_DB' in self._legacyConfigs and os.path.basename(filename) == 'defaults.ini':
            self._logger.warn("Configuration using settings.py has been deprecated, database configuration should be moved to /etc/ams.ini or ~/ams.ini")
            self._using_legacy = True

        try:
            TRACKING_DB['host'] = config.get('TRACKING_DB', 'host')
            TRACKING_DB['port'] = int(config.get('TRACKING_DB', 'port'))
            TRACKING_DB['user'] = config.get('TRACKING_DB', 'user')
            TRACKING_DB['pass'] = config.get('TRACKING_DB', 'pass')
            TRACKING_DB['dbname'] = config.get('TRACKING_DB', 'dbname')
            self._iniconfigs['TRACKING_DB'] = TRACKING_DB
            if self._using_legacy:
                self.TRACKING_DB = self._legacyConfigs['TRACKING_DB']
                self._sources['TRACKING_DB'] = 'legacy settings.py'
            else:
                self.TRACKING_DB = TRACKING_DB
                self._sources['TRACKING_DB'] = filename

            # these have to be explicitly defined here since we can't have read data from the database yet
            self.TRACKING_DB['host'] = self.env('AMS_DB_HOST', self.TRACKING_DB['host'])
            self.TRACKING_DB['user'] = self.env('AMS_DB_HOST', self.TRACKING_DB['user'])
            self.TRACKING_DB['pass'] = self.env('AMS_DB_HOST', self.TRACKING_DB['pass'])
            self.TRACKING_DB['port'] = int(self.env('AMS_DB_HOST', self.TRACKING_DB['port']))
            self.TRACKING_DB['dbname'] = self.env('AMS_DB_HOST', self.TRACKING_DB['dbname'])
        except ConfigParser.NoSectionError as e:
            if not self._using_legacy:
                raise InvalidConfigFile("Config file {0} missing section: {1}".format(filename, str(e)))
            else:
                self._logger.warn("Config file {0} missing section: {1}".format(filename, str(e)))
        except ConfigParser.NoOptionError as e:
            if not self._using_legacy:
                raise InvalidConfigFile("Config file {0} missing option: {1}".format(filename, str(e)))
            else:
                self._logger.warn("Config file {0} missing option: {1}".format(filename, str(e)))

        options = config.options('CONFIG')
        for option in options:
            self._iniconfigs[option] = config.get('CONFIG', option)


    def get_logger(self):
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger('ams')
            amsloglevel = getattr(logging, 'DEBUG')
            globalloglevel = getattr(logging, 'CRITICAL')
            logging.basicConfig(level=globalloglevel)
            self._logger.setLevel(level=amsloglevel)
        return self._logger


    def combine(self):
        finalsettings = {}
        for k,v in self._dbconfigs.iteritems():
            finalsettings[k] = v

        if os.path.basename(self._inifile) == 'defaults.ini':
            for k,v in self._iniconfigs.iteritems():
                if k in finalsettings:
                    finalsettings[k] = v or finalsettings[k]
                else:
                    finalsettings[k] = v

        for k,v in self._legacyConfigs.iteritems():
            if k in finalsettings:
                finalsettings[k] = v or finalsettings[k]
            else:
                finalsettings[k] = v

        if os.path.basename(self._inifile) != 'defaults.ini':
            for k,v in self._iniconfigs.iteritems():
                if k in finalsettings:
                    finalsettings[k] = v or finalsettings[k]
                else:
                    finalsettings[k] = v

        for k,v in self._env_overrides.iteritems():
            if k in finalsettings:
                finalsettings[k] = v or finalsettings[k]
            else:
                finalsettings[k] = v

        for k,v in finalsettings.iteritems():
            setattr(self, k, v)


    def env(self, keys, dflt):
        if keys is None:
            return dflt
        if isinstance(keys, basestring):
            keys = [ keys ]
        for key in keys:
            if os.environ.has_key(key):
                return os.environ.get(key)
        return dflt
