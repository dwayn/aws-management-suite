import pymysql.cursors
import argparse
import prettytable
import logging
from errors import *

class BaseManager(object):
    def __init__(self, settings):
        self.settings = settings
        self.dbconn = pymysql.connect(host=self.settings.TRACKING_DB['host'],
                             port=self.settings.TRACKING_DB['port'],
                             user=self.settings.TRACKING_DB['user'],
                             password=self.settings.TRACKING_DB['pass'],
                             db=self.settings.TRACKING_DB['dbname'])
        self.db = self.dbconn.cursor()
        self.logger = self.get_logger()
        self.boto_conns = {}
        self.__subinit__()
        self._az_region_map = {}

    def __subinit__(self):
        ''' Called  by the constructor to allow subclasses to have their own unique constructors '''
        pass

    def build_argument_parser(self, parser):
        if not isinstance(parser, argparse.ArgumentParser):
            raise TypeError("Expecting an ArgumentParser")
        self.argument_parser_builder(parser)

    # this must be implemented to build out the argument parser sub section for a particular module
    def argument_parser_builder(self, parser):
        raise NotImplementedError("argument_parser_builder not implemented")


    def output_formatted(self, table_title, column_headers, data, summary_text=None, insert_breaks=0):
        def tstr(x):
            if x is not None:
                return str(x)
            else:
                # gives some value for output so that command line tools like cut and awk work more easily
                return "---"

        if self.settings.HUMAN_OUTPUT:
            print "\n\n{0}:".format(table_title)
            table = prettytable.PrettyTable(column_headers)
            table.align = 'l'
            for row in data:
                table.add_row(map(tstr, row))
                for x in range(insert_breaks):
                    table.add_row([' '] * len(row))
            print table
            if summary_text:
                print "{0}\n".format(summary_text)
            else:
                print "{0} total records\n".format(len(data))
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
        if availability_zone not in self._az_region_map:
            self.db.execute("select region from availability_zones where availability_zone = %s", (availability_zone, ))
            row = self.db.fetchone()
            if not row:
                raise InvalidValue("Availability zone not found, to load availability zone data try running: ams host discovery")
            self._az_region_map[availability_zone] = row[0]
        return self._az_region_map[availability_zone]

    def argparse_stub(self):
        raise NotImplemented('argparse_stub() must be implemented for dynamic modules')

    def argparse_help_text(self):
        return ''

