import MySQLdb
import argparse


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

    def build_argument_parser(self, parser):
        if not isinstance(parser, argparse.ArgumentParser):
            raise TypeError("Expecting an ArgumentParser")
        self.argument_parser_builder(parser)

    # this must be implemented to build out the argument parser sub section for a particular module
    def argument_parser_builder(self, parser):
        raise NotImplementedError("__argument_parser_builder not implemented")

