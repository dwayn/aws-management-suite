import boto
from amslib.core.manager import BaseManager


class Route53Manager(BaseManager):

    def __get_boto_conn(self):
        if 'rout53' not in self.boto_conns:
            self.boto_conns["route53"] = boto.route53.connection.Route53Connection(aws_access_key_id=self.settings.AWS_ACCESS_KEY, aws_secret_access_key=self.settings.AWS_SECRET_KEY)
        return self.boto_conns["route53"]


    def discovery(self):
        self.logger.error("Route53 discovery not implemented yet")
        pass


    def argument_parser_builder(self, parser):
        rsubparser = parser.add_subparsers(title="action", dest='action')

        discparser = rsubparser.add_parser("discovery", help="Run discovery on route53 to populate database with DNS data")
        discparser.set_defaults(func=self.command_discover)



    def command_discover(self, args):
        self.discovery()
        pass



