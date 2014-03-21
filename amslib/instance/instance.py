import time
import re
import os
import prettytable
import boto.ec2
import argparse
from amslib.core.manager import BaseManager
from amslib.ssh.sshmanager import SSHManager
# from errors import *


class InstanceManager(BaseManager):

    def __get_boto_conn(self, region):
        if region not in self.boto_conns:
            self.boto_conns[region] = boto.ec2.connect_to_region(region, aws_access_key_id=self.settings.AWS_ACCESS_KEY, aws_secret_access_key=self.settings.AWS_SECRET_KEY)
        return self.boto_conns[region]






    def discover(self):
        regions = boto.ec2.regions()
        for region in regions:
            print region.name
            botoconn = self.__get_boto_conn(region.name)
            print "getting instances"
            try:
                instances = botoconn.get_only_instances()
            except boto.exception.EC2ResponseError:
                continue
            for i in instances:
                print "Found instance {0}".format(i.id)
                name = None
                if 'Name' in i.tags:
                    name = i.tags['Name']
                self.db.execute("insert into hosts set instance_id=%s, host=%s, hostname_internal=%s, hostname_external=%s, "
                                "ip_internal=%s, ip_external=%s, ami_id=%s, instance_type=%s, availability_zone=%s, name=%s on duplicate "
                                "key update hostname_internal=%s, hostname_external=%s, ip_internal=%s, ip_external=%s, ami_id=%s, "
                                "instance_type=%s, availability_zone=%s, name=%s", (i.id, i.dns_name, i.private_dns_name, i.public_dns_name,
                                                                            i.private_ip_address, i.ip_address, i.image_id, i.instance_type,
                                                                            i.placement, name, i.private_dns_name, i.public_dns_name, i.private_ip_address,
                                                                            i.ip_address, i.image_id, i.instance_type, i.placement, name))
                self.dbconn.commit()
        pass

    def argument_parser_builder(self, parser):

        hsubparser = parser.add_subparsers(title="action", dest='action')

        # ams host list
        hlistparser = hsubparser.add_parser("list", help="list currently managed hosts")
        hlistparser.add_argument('search_field', nargs="?", help="field to search (host or instance_id)", choices=['host', 'instance_id'])
        hlistparser.add_argument('field_value', nargs="?", help="exact match search value")
        hlistparser.add_argument("--like", help="string to find within 'search-field'")
        hlistparser.add_argument("--prefix", help="string to prefix match against 'search-field'")
        hlistparser.add_argument("--zone", help="Availability zone to filter results by. This is a prefix search so any of the following is valid with increasing specificity: 'us', 'us-west', 'us-west-2', 'us-west-2a'")
        hlistparser.set_defaults(func=self.command_host_list)

        # ams host add
        haddparser = hsubparser.add_parser("add", help="Add host to the database to be managed")
        haddparser.add_argument('-i', '--instance', help="Instance ID of the instance to add", required=True)
        haddparser.add_argument('-H', '--hostname', help="hostname of the host (used to ssh to the host to do management)", required=True)
        haddparser.add_argument('-z', '--zone', help="availability zone that the instance is in", required=True)
        haddparser.add_argument('--hostname-internal', help="internal hostname (stored but not currently used)")
        haddparser.add_argument('--hostname-external', help="external hostname (stored but not currently used)")
        haddparser.add_argument('--ip-internal', help="internal IP address (stored but not currently used)")
        haddparser.add_argument('--ip-external', help="external IP address (stored but not currently used)")
        haddparser.add_argument('--ami-id', help="AMI ID (stored but not currently used)")
        haddparser.add_argument('--instance-type', help="Instance type (stored but not currently used)")
        haddparser.add_argument('--notes', help="Notes on the instance/host (stored but not currently used)")
        haddparser.set_defaults(func=self.command_host_add)

        discparser = hsubparser.add_parser("discovery", help="Run discovery on hosts/instances to populate database with resources")
        discparser.set_defaults(func=self.command_discover)

    def command_discover(self, args):
        self.discover()

    def command_host_list(self, args):
        whereclauses = []
        order_by = ''
        if args.search_field:
            if args.field_value:
                whereclauses.append("{0} = '{1}'".format(args.search_field, args.field_value))
            elif args.like:
                whereclauses.append("{0} like '%{1}%'".format(args.search_field, args.like))
            elif args.prefix:
                whereclauses.append("{0} like '%{1}%'".format(args.search_field, args.prefix))
            order_by = ' order by {0}'.format(args.search_field)
        if args.zone:
            whereclauses.append("availability_zone like '{0}%'".format(args.zone))
            if not order_by:
                order_by = ' order by availability_zone'

        sql = "select host, instance_id, availability_zone, name, notes from hosts"
        if len(whereclauses):
            sql += " where " + " and ".join(whereclauses)
        sql += order_by
        self.db.execute(sql)
        results = self.db.fetchall()

        if self.settings.human_output:
            print "\n\nHosts:"
            table = prettytable.PrettyTable(["Hostname", "instance_id", "availability_zone", "name", "notes"])
            for res in results:
                table.add_row(res)
            print table
            print "\n\n"
        else:
            for res in results:
                print "{0}\t{1}\t{2}\t{3}\t{4}".format(res[0], res[1], res[2], res[3], res[4])


    def command_host_add(self, args):
        self.db.execute("insert into hosts(`instance_id`, `host`, `availability_zone`, `hostname_internal`, `hostname_external`, `ip_internal`, "
                   "`ip_external`, `ami_id`, `instance_type`, `notes`) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (args.instance,
                                                                                                         args.hostname,
                                                                                                         args.zone,
                                                                                                         args.hostname_internal,
                                                                                                         args.hostname_external,
                                                                                                         args.ip_internal,
                                                                                                         args.ip_external,
                                                                                                         args.ami_id,
                                                                                                         args.instance_type,
                                                                                                         args.notes))
        self.dbconn.commit()
        print "Added instance {0}({1}) to list of managed hosts".format(args.hostname, args.instance)
