import boto
from amslib.core.manager import BaseManager
import pprint

pp = pprint.PrettyPrinter(indent=4)

class Route53Manager(BaseManager):

    def __get_boto_conn(self):
        if 'rout53' not in self.boto_conns:
            self.boto_conns["route53"] = boto.connect_route53(aws_access_key_id=self.settings.AWS_ACCESS_KEY, aws_secret_access_key=self.settings.AWS_SECRET_KEY)
        return self.boto_conns["route53"]


    #TODO implement interactive mode
    #TODO need to figure out how to handle a host in multiple zones (possible: preferred zone, and handling in interactive)
    def discovery(self, prefer_hostname='external', interactive=False, load_route53_only=False):
        botoconn = self.__get_boto_conn()
        zonesdata = botoconn.get_all_hosted_zones()
        for zd in zonesdata['ListHostedZonesResponse']['HostedZones']:
            comment = None
            if "Comment" in zd['Config']:
                comment = zd['Config']['Comment']
            self.db.execute("replace into route53_zones set zone_id=%s, name=%s, record_sets=%s, comment=%s", (zd['Id'].replace('/hostedzone/',''), zd['Name'], zd['ResourceRecordSetCount'], comment))
            self.dbconn.commit()
            self.logger.debug(zd)
        # pp.pprint(zonesdata)
        zones = botoconn.get_zones()
        for z in zones:
            recs = z.get_records()
            zone_id = recs.hosted_zone_id

            # since we are pulling a complete list every time, we do not need records that exist prior to this load step
            self.db.execute("truncate route53_records")
            self.dbconn.commit()
            # if identifier is set, then the record is one of WRR, latency or failover. WRR will include a value for weight,
            #   latency will include a value for region, and failover will not include weight or region #TODO verify assumption on failover
            for r in recs:
                name = r.name
                #TODO need to find out if i could ever get relative hostnames (rather than fqdn) back from this API call
                if name[len(name)-1] == '.':
                    name = name[0:len(name)-1]
                ident = r.identifier
                if not r.identifier:
                    ident = ""
                self.db.execute("insert into route53_records set zone_id=%s, name=%s, type=%s, identifier=%s, resource_records=%s, ttl=%s, alias_hosted_zone_id=%s, alias_dns_name=%s, weight=%s, region=%s",
                                (zone_id, name, r.type, ident, "\n".join(r.resource_records), r.ttl, r.alias_hosted_zone_id, r.alias_dns_name, r.weight, r.region))
                self.dbconn.commit()
                self.logger.info("Found {0} record for {1}".format(r.type, r.name))

        if not load_route53_only:
            self.db.execute("select instance_id, host, ip_internal, ip_external, hostname_internal, hostname_external from hosts")
            hosts = self.db.fetchall()
            if not hosts:
                self.logger.warning("No hosts found, try running: ams host discovery")
                return

            for host in hosts:
                if not (host[2] or host[3] or host[4] or host[5]):
                    continue
                hostname = None
                if prefer_hostname == 'internal':
                    if not hostname:
                        hostname = self.get_fqdn_for_host(host[2])
                    if not hostname:
                        hostname = self.get_fqdn_for_host(host[4])
                    if not hostname:
                        hostname = self.get_fqdn_for_host(host[3])
                    if not hostname:
                        hostname = self.get_fqdn_for_host(host[5])
                elif prefer_hostname == 'external':
                    if not hostname:
                        hostname = self.get_fqdn_for_host(host[3])
                    if not hostname:
                        hostname = self.get_fqdn_for_host(host[5])
                    if not hostname:
                        hostname = self.get_fqdn_for_host(host[2])
                    if not hostname:
                        hostname = self.get_fqdn_for_host(host[4])
                if hostname:
                    self.logger.info("Found hostname for instance {0}, updating from {1} to {2}".format(host[0], host[1], hostname))
                    self.db.execute("update hosts set host=%s where instance_id=%s", (hostname, host[0]))
                    self.dbconn.commit()



    def get_fqdn_for_host(self, host_or_ip):
        self.db.execute("select name from route53_records where identifier = '' and type in ('A', 'CNAME') and resource_records = %s", (host_or_ip,))
        row = self.db.fetchone()
        if not row:
            return None
        name = row[0]
        return name


    def argument_parser_builder(self, parser):
        rsubparser = parser.add_subparsers(title="action", dest='action')

        # ams route53 discovery
        discparser = rsubparser.add_parser("discovery", help="Run discovery on route53 to populate database with DNS data")
        discparser.add_argument("--interactive", help="Enable interactive mode for applying discovered host names to hosts (not enabled yet)", action='store_true')
        discparser.add_argument("--prefer", default='external', choices=['internal', 'external'], help="Sets which hostname gets preference if DNS records are defined for an internal address and an external address")
        discparser.add_argument("--load-only", help="Only load the route53 tables, but do not apply hostname changes to hosts", action='store_true')
        discparser.set_defaults(func=self.command_discover)



    def command_discover(self, args):
        self.discovery(args.prefer, args.interactive, args.load_only)



