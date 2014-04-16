import boto
from amslib.core.manager import BaseManager
import argparse
import pprint

pp = pprint.PrettyPrinter(indent=4)


# Custom HealthCheck object to add support for failure threshold...seems to have been missed in boto
class HealthCheck(object):

    """An individual health check"""

    POSTXMLBody = """
        <HealthCheckConfig>
            <IPAddress>%(ip_addr)s</IPAddress>
            <Port>%(port)s</Port>
            <Type>%(type)s</Type>
            <ResourcePath>%(resource_path)s</ResourcePath>
            %(fqdn_part)s
            %(string_match_part)s
            %(request_interval)s
            %(failure_threshold)s
        </HealthCheckConfig>
    """

    XMLFQDNPart = """<FullyQualifiedDomainName>%(fqdn)s</FullyQualifiedDomainName>"""

    XMLStringMatchPart = """<SearchString>%(string_match)s</SearchString>"""

    XMLRequestIntervalPart = """<RequestInterval>%(request_interval)d</RequestInterval>"""

    XMLRequestFailurePart = """<FailureThreshold>%(failure_threshold)d</FailureThreshold>"""

    valid_request_intervals = (10, 30)

    valid_failure_thresholds = range(1, 11)  # valid values are integers 1-10

    def __init__(self, ip_addr, port, hc_type, resource_path, fqdn=None, string_match=None, request_interval=30, failure_threshold=3):
        """
        HealthCheck object

        :type ip_addr: str
        :param ip_addr: IP Address

        :type port: int
        :param port: Port to check

        :type hc_type: str
        :param ip_addr: One of HTTP | HTTPS | HTTP_STR_MATCH | HTTPS_STR_MATCH | TCP

        :type resource_path: str
        :param resource_path: Path to check

        :type fqdn: str
        :param fqdn: domain name of the endpoint to check

        :type string_match: str
        :param string_match: if hc_type is HTTP_STR_MATCH or HTTPS_STR_MATCH, the string to search for in the response body from the specified resource

        :type request_interval: int
        :param request_interval: The number of seconds between the time that Amazon Route 53 gets a response from your endpoint and the time that it sends the next health-check request.

        :type failure_threshold: int
        :param failure_threshold: The number of times that Amazon Route 53 that a health check has fails before the resource is marked as down.

        """
        self.ip_addr = ip_addr
        self.port = port
        self.hc_type = hc_type
        self.resource_path = resource_path
        self.fqdn = fqdn
        self.string_match = string_match

        if failure_threshold in self.valid_failure_thresholds:
            self.failure_threshold = failure_threshold
        else:
            raise AttributeError(
                "Valid values for request_interval are: %s" %
                ",".join(str(i) for i in self.valid_failure_thresholds))

        if request_interval in self.valid_request_intervals:
            self.request_interval = request_interval
        else:
            raise AttributeError(
                "Valid values for request_interval are: %s" %
                ",".join(str(i) for i in self.valid_request_intervals))

    def to_xml(self):
        params = {
            'ip_addr': self.ip_addr,
            'port': self.port,
            'type': self.hc_type,
            'resource_path': self.resource_path,
            'fqdn_part': "",
            'string_match_part': "",
            'request_interval': (self.XMLRequestIntervalPart %
                                 {'request_interval': self.request_interval}),
            'failure_threshold': (self.XMLRequestFailurePart %
                                 {'failure_threshold': self.failure_threshold}),
        }
        if self.fqdn is not None:
            params['fqdn_part'] = self.XMLFQDNPart % {'fqdn': self.fqdn}

        if self.string_match is not None:
            params['string_match_part'] = self.XMLStringMatchPart % {'string_match' : self.string_match}

        return self.POSTXMLBody % params



class Route53Manager(BaseManager):

    def __get_boto_conn(self):
        if 'rout53' not in self.boto_conns:
            self.boto_conns["route53"] = boto.connect_route53(aws_access_key_id=self.settings.AWS_ACCESS_KEY, aws_secret_access_key=self.settings.AWS_SECRET_KEY)
            ################-------------START MONKEYPATCH-------------#####################
            # this is a terrible thing to have to do, but I had to monkeypatch this to get it to work until new version of boto
            # comes out that addresses the missing health_check field addressed in this pull request
            # https://github.com/jzbruno/boto/commit/075634f49441ff293e1717d44c04862b257f65c6
            def boto_route53_record_Record_endElement(self, name, value, connection):
                if name == 'Name':
                    self.name = value
                elif name == 'Type':
                    self.type = value
                elif name == 'TTL':
                    self.ttl = value
                elif name == 'Value':
                    self.resource_records.append(value)
                elif name == 'HostedZoneId':
                    self.alias_hosted_zone_id = value
                elif name == 'DNSName':
                    self.alias_dns_name = value
                elif name == 'SetIdentifier':
                    self.identifier = value
                elif name == 'EvaluateTargetHealth':
                    self.alias_evaluate_target_health = value
                elif name == 'Weight':
                    self.weight = value
                elif name == 'Region':
                    self.region = value
                # the following 2 lines are all that this differs from boto 2.27.0
                elif name == 'HealthCheckId':
                    self.health_check = value

            boto.route53.record.Record.endElement = boto_route53_record_Record_endElement
            ################-------------END MONKEYPATCH-------------#####################
        return self.boto_conns["route53"]


    #TODO implement interactive mode
    #TODO need to figure out how to handle a host in multiple zones (possible: preferred zone, and handling in interactive)
    def discovery(self, prefer_hostname='external', interactive=False, load_route53_only=False):
        botoconn = self.__get_boto_conn()
        health_checks = botoconn.get_list_health_checks()
        # type can be one of the following strings: HTTP | HTTPS | HTTP_STR_MATCH | HTTPS_STR_MATCH | TCP
        for health_check in health_checks['ListHealthChecksResponse']['HealthChecks']:
            resource_path = None
            if 'ResourcePath' in health_check['HealthCheckConfig']:
                resource_path = health_check['HealthCheckConfig']['ResourcePath']
            search_string = None
            if 'SearchString' in health_check['HealthCheckConfig']:
                search_string = health_check['HealthCheckConfig']['SearchString']
            fqdn = None
            if 'FullyQualifiedDomainName' in health_check['HealthCheckConfig']:
                fqdn = health_check['HealthCheckConfig']['FullyQualifiedDomainName']

            self.logger.info("Found health check: {0}://{1}:{2}".format(health_check['HealthCheckConfig']['Type'], health_check['HealthCheckConfig']['IPAddress'], health_check['HealthCheckConfig']['Port']))
            self.db.execute("insert into route53_healthchecks set healthcheck_id=%s, ip=%s, port=%s, type=%s, request_interval=%s, "
                            "failure_threshold=%s, resource_path=%s, search_string=%s, fqdn=%s, caller_reference=%s "
                            "on duplicate key update ip=%s, port=%s, type=%s, request_interval=%s, failure_threshold=%s, "
                            "resource_path=%s, search_string=%s, fqdn=%s, caller_reference=%s",
                            (health_check['Id'], health_check['HealthCheckConfig']['IPAddress'], health_check['HealthCheckConfig']['Port'],
                             health_check['HealthCheckConfig']['Type'], health_check['HealthCheckConfig']['RequestInterval'],
                             health_check['HealthCheckConfig']['FailureThreshold'], resource_path, search_string, fqdn, health_check['CallerReference'],
                             health_check['HealthCheckConfig']['IPAddress'], health_check['HealthCheckConfig']['Port'], health_check['HealthCheckConfig']['Type'],
                             health_check['HealthCheckConfig']['RequestInterval'], health_check['HealthCheckConfig']['FailureThreshold'],
                             resource_path, search_string, fqdn, health_check['CallerReference']))
            self.dbconn.commit()

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
        self.logger.debug(zones)
        # since we are pulling a complete list every time, we do not need records that exist prior to this load step #TODO should possibly implement more atomic way of doing this
        self.db.execute("truncate route53_records")
        self.dbconn.commit()
        for z in zones:
            self.logger.debug(z)
            recs = z.get_records()
            zone_id = recs.hosted_zone_id

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
                self.db.execute("insert into route53_records set zone_id=%s, name=%s, type=%s, identifier=%s, resource_records=%s, ttl=%s, alias_hosted_zone_id=%s, alias_dns_name=%s, weight=%s, region=%s, healthcheck_id=%s",
                                (zone_id, name, r.type, ident, "\n".join(r.resource_records), r.ttl, r.alias_hosted_zone_id, r.alias_dns_name, r.weight, r.region, r.health_check))
                self.dbconn.commit()
                self.logger.info("Found {0} record for {1}".format(r.type, r.name))

        if not load_route53_only:
            self.db.execute("select instance_id, host, ip_internal, ip_external, hostname_internal, hostname_external from hosts")
            hosts = self.db.fetchall()
            if not hosts:
                self.logger.warning("No hosts found, try running: ams host discovery")
                return
            self.logger.debug("number of hosts {0}".format(len(hosts)))
            for host in hosts:
                if not (host[2] or host[3] or host[4] or host[5]):
                    # self.logger.debug("Skipping {0}({1}) as it has no hostname or ip information".format(host[1], host[0]))
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
        if not host_or_ip:
            return None
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

        listparser = rsubparser.add_parser("list", help="List Route53 DNS information currently in the database")
        listparser.add_argument("resource", nargs='?', default="dns", choices=["dns", "healthchecks"], help="Resource type to list")
        listparser.set_defaults(func=self.command_list)

        adddnssharedargs = argparse.ArgumentParser(add_help=False)
        adddnssharedargs.add_argument('fqdns', help="Fully qualified dns name for the entry. You can include the trailing dot(.) or it will be added automatically")
        adddnssharedargs.add_argument('record_type', help="DNS record type (currently only support A and CNAME)", choices=['a', 'cname'])
        group = adddnssharedargs.add_mutually_exclusive_group(required=True)
        group.add_argument('--zone-id', help="Zone id to add DNS record to")
        group.add_argument('--zone-name', help="Zone name to add DNS record to")
        adddnssharedargs.add_argument('-t', '--ttl', help="TTL for the entry (default: 60)", type=int, default=60)
        adddnssharedargs.add_argument('-r', '--routing-policy', help='The routing policy to use (default: simple)', choices=['simple', 'weighted', 'latency', 'failover'], default='simple')
        adddnssharedargs.add_argument('-w', '--weight', type=int, help="Weighted routing policy: weight to assign to the dns resource")
        adddnssharedargs.add_argument('--region', help="Latency routing policy: assigns the region for the dns resource for routing")
        adddnssharedargs.add_argument('--health-check', type=int, help="health check id to associate with the record (for IDs, use: ams route53 list healthchecks)")
        adddnssharedargs.add_argument('--failover-role', help="Failover routing policy: defines whether resource is primary or secondary", choices=['primary','secondary'], default='primary')

        dnsparser = rsubparser.add_parser("dns", help="DNS management operations")
        dnssubparser = dnsparser.add_subparsers(title="operation", dest="operation")

        creatednsparser = dnssubparser.add_parser("create", help="Create new DNS entry", parents=[adddnssharedargs])
        creatednsparser.add_argument('-v', '--record-value', help="Value for the DNS record (Currently only has support single value entries)")
        creatednsparser.add_argument('--identifier', help="Unique identifier to associate to a record that shares a name/type with other records in weighted, latency, or failover records")
        creatednsparser.set_defaults(func=self.command_not_implemented)

        adddnsparser = dnssubparser.add_parser("add", help="add dns entries for host/instance", parents=[adddnssharedargs])
        group = adddnsparser.add_mutually_exclusive_group(required=True)
        group.add_argument('-H', '--host', help="Hostname (to find current hostname use: ams host list)")
        group.add_argument('-i', '--instance', help="Instance ID")
        adddnsparser.add_argument('--use', help="Define whether to use the public or private hostname/IP", choices=["public", "private"], default="public")
        adddnsparser.add_argument('--identifier', help="Unique identifier to associate to a record that shares a name/type with other records in weighted, latency, or failover records. If not provided, one will be created from the hostname or instance id")
        adddnsparser.add_argument('--hc', action='store_true', help="Create a Route53 health check for host")
        adddnsparser.add_argument('--hc-port', type=int, help="Health check port")
        adddnsparser.add_argument('--hc-type', help="Health check type", choices=['tcp', 'http', 'https'])
        adddnsparser.add_argument('--hc-interval', type=int, help="Health check interval (10 or 30 second)", choices=[10,30], default=30)
        adddnsparser.add_argument('--hc-threshold', type=int, help="Number of times health check fails before the host is marked down by Route53", choices=range(1, 11), default=3)
        adddnsparser.add_argument('--hc-path', help="HTTP/HTTPS: health check resource path")
        adddnsparser.add_argument('--hc-fqdn', help="HTTP/HTTPS: health check fully qualified domain name")
        adddnsparser.add_argument('--hc-match', help="HTTP/HTTPS: health check response match string")
        adddnsparser.set_defaults(func=self.command_add_dns)

        updatednsparser = dnssubparser.add_parser("update", help="Update a DNS entry")
        updatednsparser.set_defaults(func=self.command_not_implemented)
        deletednsparser = dnssubparser.add_parser("delete", help="Delete a DNS entry")
        deletednsparser.set_defaults(func=self.command_not_implemented)


        healthparser = rsubparser.add_parser("healthchecks", help="Route53 healthcheck management operations")
        healthsubparser = healthparser.add_subparsers(title="operation", dest="operation")
        createhealthparser = healthsubparser.add_parser("create", help="Create a new health check")
        createhealthparser.set_defaults(func=self.command_not_implemented)
        updatehealthparser = healthsubparser.add_parser("update", help="Update a health check")
        updatehealthparser.set_defaults(func=self.command_not_implemented)
        deletehealthparser = healthsubparser.add_parser("delete", help="Delete a health check")
        deletehealthparser.set_defaults(func=self.command_not_implemented)

    def command_add_dns(self, args):
        if args.host:
            whereclause = "host=%s"
            wherevar = args.host
        elif args.instance:
            whereclause = "instance_id=%s"
            wherevar = args.instance

        self.db.execute("select instance_id, host, hostname_internal, hostname_external, ip_internal, ip_external, availability_zone from hosts where {0} and `terminated`=0".format(whereclause), (wherevar, ))
        row = self.db.fetchone()
        if not row:
            self.logger.error("{0} not found".format(wherevar))
            return

        if args.use == 'public':
            cname_entry = row[3]
            ip_entry = row[5]
        elif args.use == 'private':
            cname_entry = row[2]
            ip_entry = row[4]

        if args.record_type == 'a':
            entry_value = ip_entry
        elif args.record_type == 'cname':
            entry_value = cname_entry

        self.logger.error("Command not fully implemented: no action taken")

    def command_create_dns(self, args):

        pass

    def command_create_health_check(self, args):

        pass

    def command_not_implemented(self, args):
        self.logger.error("Function not implemented yet")

    def command_discover(self, args):
        self.discovery(args.prefer, args.interactive, args.load_only)

    def command_list(self, args):
        if args.resource == "dns":
            self.db.execute("select r.name, r.type, r.weight, r.region, r.identifier, r.zone_id, z.name, r.resource_records, if(h.id is not null, concat(h.type,'://',h.ip,':',h.port, ' (', h.id,')'), null) from route53_zones z join route53_records r using(zone_id) left join route53_healthchecks h using (healthcheck_id) order by r.name")
            rows = self.db.fetchall()
            headers = ['fqdns', 'type', 'weight', 'region', 'identifier', 'zone id', 'zone name', 'resource records', 'health check (id)']
            self.output_formatted("Route53 DNS", headers, rows)

        elif args.resource == "healthchecks":
            self.db.execute("select id, ip, port, type, request_interval, failure_threshold, resource_path, search_string, fqdn from route53_healthchecks")
            rows = self.db.fetchall()
            headers = ['id', 'ip', 'port', 'type', 'request interval', 'failure threshold', 'resource path', 'search string', 'fqdn']
            self.output_formatted("Route53 Health Checks", headers, rows)



