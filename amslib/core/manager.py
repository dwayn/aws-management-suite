import MySQLdb

class BaseManager:
    def __init__(self, settings):
        self.settings = settings
        self.__dbconn = MySQLdb.connect(host=self.settings.TRACKING_DB['host'],
                             port=self.settings.TRACKING_DB['port'],
                             user=self.settings.TRACKING_DB['user'],
                             passwd=self.settings.TRACKING_DB['pass'],
                             db=self.settings.TRACKING_DB['dbname'])
        self.__db = self.__dbconn.cursor()

        self.__boto_conns = {}
