import MySQLdb
import argparse
import prettytable


class BaseManager:
    def __init__(self, settings):
        self.settings = settings
        self.dbconn = MySQLdb.connect(host=self.settings.TRACKING_DB['host'],
                             port=self.settings.TRACKING_DB['port'],
                             user=self.settings.TRACKING_DB['user'],
                             passwd=self.settings.TRACKING_DB['pass'],
                             db=self.settings.TRACKING_DB['dbname'])
        self.db = self.dbconn.cursor()

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
                return ""

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

        pass