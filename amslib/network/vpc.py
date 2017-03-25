import boto
from boto import vpc
from amslib.core.manager import BaseManager
from amslib.instance.instance import InstanceManager
import argparse
from errors import *
import json
from pprint import pprint
import time
from amslib.core.completion import ArgumentCompletion


class VpcManager(BaseManager):

    def __get_boto_conn(self, region):
        if region not in self.boto_conns:
            self.boto_conns[region] = vpc.connect_to_region(region, aws_access_key_id=self.settings.getRegionalSetting(region, 'AWS_ACCESS_KEY'), aws_secret_access_key=self.settings.getRegionalSetting(region, 'AWS_SECRET_KEY'))
        return self.boto_conns[region]

    def ip_to_int(self, ipaddress):
        return reduce(lambda a, b: a << 8 | b, map(int, ipaddress.split(".")))

    def int_to_ip(self, num):
        return ".".join(map(lambda n: str(num >> n & 0xFF), [24, 16, 8, 0]))

    def cidr_to_int_range(self, cidr):
        baseip, nw = cidr.split('/')
        nw = 32 - int(nw)
        if not nw:
            return baseip, baseip
        i = self.ip_to_int(baseip)
        start = (i >> nw) << nw
        end = (((i >> nw) + 1) << nw) - 1
        return start, end

    def discovery(self, filter_region=None):
        if filter_region:
            regions = [boto.ec2.get_region(filter_region)]
        else:
            regions = boto.ec2.regions()
        for region in regions:
            try:
                self.logger.info("Processing region: {0}".format(region.name))
                botoconn = self.__get_boto_conn(region.name)
                vpcs = botoconn.get_all_vpcs()
                self.db.execute("update vpcs set active=0 where region=%s", (region.name, ))
                self.db.execute("update subnets set active=0 where availability_zone like %s", ("{0}%".format(region.name), ))
                self.dbconn.commit()
                for v in vpcs:
                    start, end = self.cidr_to_int_range(v.cidr_block)
                    self.logger.info("VPC: {0}".format(v.id))
                    self.db.execute("insert into vpcs set vpc_id=%s, region=%s, cidr=%s, is_default=%s, start_inet=%s, end_inet=%s, active=1 "
                                    "on duplicate key update region=%s, cidr=%s, is_default=%s, start_inet=%s, end_inet=%s, active=1",
                                    (v.id, region.name, v.cidr_block, v.is_default, start, end, region.name, v.cidr_block, v.is_default, start, end))
                    self.dbconn.commit()

                subnets = botoconn.get_all_subnets()
                for subnet in subnets:
                    start, end = self.cidr_to_int_range(subnet.cidr_block)
                    self.logger.info("Subnet: {0} ({1})".format(subnet.id, subnet.cidr_block))
                    self.db.execute("insert into subnets set subnet_id=%s, vpc_id=%s, cidr=%s, availability_zone=%s, start_inet=%s, end_inet=%s, active=1 "
                                    "on duplicate key update vpc_id=%s, cidr=%s, availability_zone=%s, start_inet=%s, end_inet=%s, active=1",
                                    (subnet.id, subnet.vpc_id, subnet.cidr_block, subnet.availability_zone, start, end,
                                     subnet.vpc_id, subnet.cidr_block, subnet.availability_zone, start, end))
                    self.dbconn.commit()

                self.db.execute("delete from vpcs where region=%s and active=0", (region.name, ))
                self.db.execute("delete from subnets where availability_zone like %s and active=0", ("{0}%".format(region.name), ))
                self.dbconn.commit()

            except boto.exception.EC2ResponseError as e:
                if e.code != 'AuthFailure':
                    raise




    def argparse_stub(self):
        return "vpc"


    def argparse_help_text(self):
        return 'VPC management functionality'


    def argument_parser_builder(self, parser):
        ac = ArgumentCompletion(self.settings)

        rsubparser = parser.add_subparsers(title="action", dest='action')

        # ams vpc discovery
        discparser = rsubparser.add_parser("discovery", help="Run discovery to gather current VPC configurations")
        discparser.add_argument('-r', '--region', help="Limit discover to given region").completer = ac.region
        discparser.set_defaults(func=self.command_discover)

        # ams vpc list
        listparser = rsubparser.add_parser("list", help="List available VPCs")
        listparser.add_argument("type", nargs="?", help="Category of VPC to list", choices=['vpcs', 'subnets'], default='vpcs')
        listparser.add_argument('-v', '--vpc-id', help="Filter by VPC ID").completer = ac.vpc_id
        listparser.add_argument('-s', '--subnet-id', help="Filter by Subnet ID").completer = ac.subnet_id
        listparser.add_argument('-r', '--region', help="Filter by region").completer = ac.region
        listparser.set_defaults(func=self.command_list)


    def command_list(self, args):
        if args.type == 'vpcs':
            wheres = []
            wherevars = []
            if args.vpc_id:
                wheres.append("vpc_id=%s")
                wherevars.append(args.vpc_id)
            if args.region:
                wheres.append("region=%s")
                wherevars.append(args.region)
            sql = "select vpc_id, region, cidr, is_default, inet_ntoa(start_inet), inet_ntoa(end_inet) from vpcs "
            if wheres:
                sql += " where "
                sql += " and ".join(wheres)
            self.db.execute(sql, wherevars)
            headers = ['VPC ID', 'Region', 'CIDR', 'Default VPC', 'Start IP', 'End IP']
            rows = self.db.fetchall()
            if not rows:
                rows = []
            self.output_formatted("VPCs", headers, rows)

        if args.type == 'subnets':
            wheres = []
            wherevars = []
            if args.vpc_id:
                wheres.append("vpc_id=%s")
                wherevars.append(args.vpc_id)
            if args.region:
                wheres.append("availability_zone like %s")
                wherevars.append(args.region + "%")
            if args.subnet_id:
                wheres.append("subnet_id=%s")
                wherevars.append(args.subnet_id)

            sql = "select vpc_id, subnet_id, availability_zone, cidr, inet_ntoa(start_inet), inet_ntoa(end_inet) from subnets "
            if wheres:
                sql += " where "
                sql += " and ".join(wheres)
            sql += " order by vpc_id, subnet_id"

            self.db.execute(sql, wherevars)
            headers = ['VPC ID', 'Subnet ID', 'Availability Zone', 'CIDR', 'Start IP', 'End IP']
            rows = self.db.fetchall()
            if not rows:
                rows = []
            self.output_formatted("VPC Subnets", headers, rows)



    def command_discover(self, args):
        self.discovery(args.region)

