import MySQLdb
import argparse
import prettytable
import logging

class BaseManager:
    def __init__(self, settings):
        self.settings = settings
        self.dbconn = MySQLdb.connect(host=self.settings.TRACKING_DB['host'],
                             port=self.settings.TRACKING_DB['port'],
                             user=self.settings.TRACKING_DB['user'],
                             passwd=self.settings.TRACKING_DB['pass'],
                             db=self.settings.TRACKING_DB['dbname'])
        self.db = self.dbconn.cursor()
        self.logger = self.get_logger()
        self.boto_conns = {}

    def build_argument_parser(self, parser):
        if not isinstance(parser, argparse.ArgumentParser):
            raise TypeError("Expecting an ArgumentParser")
        self.argument_parser_builder(parser)

    # this must be implemented to build out the argument parser sub section for a particular module
    def argument_parser_builder(self, parser):
        raise NotImplementedError("argument_parser_builder not implemented")


    def output_formatted(self, table_title, column_headers, data):
        def tstr(x):
            if x is not None:
                return str(x)
            else:
                # gives some value for output so that command line tools like cut and awk work more easily
                return "---"

        if self.settings.human_output:
            print "\n\n{0}:".format(table_title)
            table = prettytable.PrettyTable(column_headers)
            table.align = 'l'
            for row in data:
                table.add_row(map(tstr, row))
            print table
            print "\n\n"
        else:
            for row in data:
                print "\t".join(map(tstr, row))


    def get_logger(self):
        if not hasattr(self.settings, 'logger'):
            self.settings.logger = logging.getLogger('ams')
            amsloglevel = getattr(logging, self.settings.AMS_LOGLEVEL.upper(), 'WARNING')
            globalloglevel = getattr(logging, self.settings.GLOBAL_LOGLEVEL.upper(), 'CRITICAL')
            logging.basicConfig(level=globalloglevel)
            self.settings.logger.setLevel(level=amsloglevel)
        return self.settings.logger

    def parse_region_from_availability_zone(self, availability_zone):
        return availability_zone[0:len(availability_zone) - 1]