import boto
from amslib.core.manager import BaseManager
from amslib.instance.instance import InstanceManager
import argparse
from errors import *
import json
from pprint import pprint
import time
from amslib.core.completion import ArgumentCompletion


class NetworkManager(BaseManager):

    def __get_boto_conn(self, region):
        if region not in self.boto_conns:
            self.boto_conns[region] = boto.ec2.connect_to_region(region, aws_access_key_id=self.settings.AWS_ACCESS_KEY, aws_secret_access_key=self.settings.AWS_SECRET_KEY)
        return self.boto_conns[region]

    def discovery(self, filter_region=None):
        if filter_region:
            regions = [boto.ec2.get_region(filter_region)]
        else:
            regions = boto.ec2.regions()
        for region in regions:
            try:
                botoconn = self.__get_boto_conn(region.name)
                self.logger.info("Processing region: {0}".format(region.name))

                addresses = botoconn.get_all_addresses()
                self.db.execute("update elastic_ips set active=0 where region=%s", (region.name, ))
                self.dbconn.commit()
                for a in addresses:
                    qryvals = [a.public_ip, region.name, a.instance_id, a.domain, a.allocation_id, a.association_id, a.network_interface_id, a.private_ip_address, region.name, a.instance_id, a.domain, a.allocation_id, a.association_id, a.network_interface_id, a.private_ip_address]
                    self.db.execute("insert into elastic_ips set public_ip=%s, region=%s, instance_id=%s, domain=%s, allocation_id=%s, association_id=%s, network_interface_id=%s, private_ip=%s on duplicate key update region=%s, instance_id=%s, domain=%s, allocation_id=%s, association_id=%s, network_interface_id=%s, private_ip=%s", qryvals)
                    self.dbconn.commit()
                self.db.execute("delete from elastic_ips where region=%s and active=0", (region.name, ))
                self.dbconn.commit()

                security_groups = botoconn.get_all_security_groups()
                self.logger.debug("Setting active=0 for {0}".format(region.name))
                self.db.execute("update security_groups set active=0 where region=%s", (region.name, ))
                self.dbconn.commit()
                for sg in security_groups:
                    qryargs = [sg.id, sg.name, sg.description, sg.vpc_id, region.name, sg.name, sg.description, sg.vpc_id, region.name]
                    self.logger.info("Processing security group: {0}({1})".format(sg.name, sg.id))
                    self.db.execute("insert into security_groups set security_group_id=%s, name=%s, description=%s, vpc_id=%s, region=%s, active=1 on duplicate key update name=%s, description=%s, vpc_id=%s, region=%s, active=1", qryargs)
                    self.dbconn.commit()
                    self.logger.debug("Setting security_group_associations.active=0 for {0}".format(sg.id))
                    self.db.execute("update security_group_associations set active=0 where security_group_id=%s", (sg.id, ))
                    self.dbconn.commit()
                    instances = sg.instances()
                    for instance in instances:
                        self.logger.debug("Adding instance SG association {0}: {1}".format(instance.id, sg.id))
                        self.db.execute("insert into security_group_associations set security_group_id=%s, instance_id=%s, active=1 on duplicate key update active=1", (sg.id, instance.id))
                        self.dbconn.commit()

                    self.logger.debug("Setting security_group_rules.active=0 for {0}".format(sg.id))
                    self.db.execute("update security_group_rules set active=0 where security_group_id=%s", (sg.id, ))
                    self.dbconn.commit()
                    for rule in sg.rules:
                        grants = []
                        for grant in rule.grants:
                            if grant.cidr_ip:
                                g = grant.cidr_ip
                            else:
                                g = grant.group_id
                            grants.append(g)
                        from_port = rule.from_port
                        if from_port is None:
                            from_port = -1
                        to_port = rule.to_port
                        if to_port is None:
                            to_port = -1
                        qryargs = [sg.id, rule.ip_protocol, from_port, to_port, json.dumps(grants), json.dumps(grants)]
                        self.logger.debug("Adding rule: {0} {1} {2} {3} {4}".format(sg.id, 'ingress', rule.ip_protocol, from_port, to_port))
                        self.db.execute("insert into security_group_rules set security_group_id=%s, type='ingress', protocol=%s, from_port=%s, to_port=%s, grants=%s, active=1 on duplicate key update grants=%s, active=1", qryargs)
                        self.dbconn.commit()

                    for rule in sg.rules_egress:
                        grants = []
                        for grant in rule.grants:
                            if grant.cidr_ip:
                                g = grant.cidr_ip
                            else:
                                g = grant.group_id
                            grants.append(g)
                        from_port = rule.from_port
                        if from_port is None:
                            from_port = -1
                        to_port = rule.to_port
                        if to_port is None:
                            to_port = -1
                        qryargs = [sg.id, rule.ip_protocol, from_port, to_port, json.dumps(grants), json.dumps(grants)]
                        self.logger.debug("Adding rule: {0} {1} {2} {3} {4}".format(sg.id, 'egress', rule.ip_protocol, from_port, to_port))
                        self.db.execute("insert into security_group_rules set security_group_id=%s, type='egress', protocol=%s, from_port=%s, to_port=%s, grants=%s, active=1 on duplicate key update grants=%s, active=1", qryargs)
                        self.dbconn.commit()

                self.logger.debug("deleting inactive security_groups")
                self.db.execute("delete from security_groups where active=0")
                self.logger.debug("deleting inactive security_group_rules")
                self.db.execute("delete from security_group_rules where active=0")
                self.logger.debug("deleting inactive security_group_associations")
                self.db.execute("delete from security_group_associations where active=0")
            except boto.exception.EC2ResponseError as e:
                if e.code != 'AuthFailure':
                    raise




    def argparse_stub(self):
        return "network"


    def argparse_help_text(self):
        return 'General networking functionality'


    def argument_parser_builder(self, parser):
        ac = ArgumentCompletion(self.settings)

        rsubparser = parser.add_subparsers(title="action", dest='action')

        # ams network discovery
        discparser = rsubparser.add_parser("discovery", help="Run discovery to gather current general networking configurations")
        discparser.add_argument('-r', '--region', help="Limit discover to given region").completer = ac.region
        discparser.set_defaults(func=self.command_discover)

        sgparser = rsubparser.add_parser("security_groups", help="Security Group operations")
        sgsubparsers = sgparser.add_subparsers(title='subaction', dest='subaction')

        sglistparser = sgsubparsers.add_parser("list", help="List security groups")
        sglistparser.add_argument('-r', '--region', help="Filter security groups by region").completer = ac.region
        sglistparser.add_argument('-s', '--security-group', help="Filter by security group id").completer = ac.security_group_id
        sglistparser.add_argument('-n', '--name', help="Filter by security group name").completer = ac.security_group_name
        sglistparser.add_argument('-v', '--vpc', help="Filter by VPC id").completer = ac.security_group_vpc
        sglistparser.set_defaults(func=self.command_sg_list)

        eipparser = rsubparser.add_parser("elastic_ips", help="Elastic IP operations")
        eipsubparsers = eipparser.add_subparsers(title='subaction', dest='subaction')

        eiplistparser = eipsubparsers.add_parser("list", help="List elastic IPs")
        eiplistparser.add_argument('-r', '--region', help="Filter elastic IPs by region").completer = ac.region
        eiplistparser.set_defaults(func=self.command_eip_list)

    def command_eip_list(self, args):
        where = ''
        wherevals = []
        if args.region:
            where = 'where elastic_ips.region=%s'
            wherevals.append(args.region)
        self.db.execute("select public_ip, region, concat(hosts.name, ' (',elastic_ips.instance_id,')'), domain, private_ip from elastic_ips left join hosts using(instance_id) {0}".format(where), wherevals)
        rows = self.db.fetchall()
        if not rows:
            rows = []
        headers = ['Public IP', 'Region', 'Host', 'Domain', 'Private IP']
        self.output_formatted('Elastic IP Addresses', headers, rows, None, 1)

    def command_discover(self, args):
        self.discovery(args.region)

    def command_sg_list(self, args):
        wheres = []
        wherevals = []
        if args.security_group:
            wheres.append('name = %s')
            wherevals.append(args.name)
        else:
            if args.name:
                wheres.append('name = %s')
                wherevals.append(args.name)
            if args.region:
                wheres.append('region = %s')
                wherevals.append(args.region)
            if args.vpc:
                wheres.append('vpc_id = %s')
                wherevals.append(args.vpc)

        where = ""
        if len(wheres):
            where = "where " + " and ".join(wheres)
        sql = "select security_group_id, region, vpc_id, name, description from security_groups " + where
        self.db.execute(sql, wherevals)
        headers = ['security_group_id', 'region', 'vpc_id', 'name', 'description']
        rows = self.db.fetchall()
        if not rows:
            rows = []
        self.output_formatted("Security Groups", headers, rows)





