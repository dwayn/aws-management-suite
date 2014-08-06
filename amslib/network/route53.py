import boto
from amslib.core.manager import BaseManager
from amslib.instance.instance import InstanceManager
import argparse
from errors import *
import pprint
import time

pp = pprint.PrettyPrinter(indent=4)


# Custom HealthCheck object to add support for failure threshold...seems to have been missed in boto
class HealthCheck(object):

    """An individual health check"""

    POSTXMLBody = """
        <HealthCheckConfig>
            <IPAddress>%(ip_addr)s</IPAddress>
            <Port>%(port)s</Port>
            <Type>%(type)s</Type>
            %(resource_path)s
            %(fqdn_part)s
            %(string_match_part)s
            %(request_interval)s
            %(failure_threshold)s
        </HealthCheckConfig>
    """

    XMLResourcePathPart = """<ResourcePath>%(resource_path)s</ResourcePath>"""

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
            'resource_path': "",
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

        if self.resource_path is not None:
            params['resource_path'] = self.XMLResourcePathPart % {'resource_path' : self.resource_path}

        return self.POSTXMLBody % params

# custom version of the boto.route53.record.Record module to add support for failover resource records and to fix the missing health chech field on a response
class Record(object):
    """An individual ResourceRecordSet"""

    HealthCheckBody = """<HealthCheckId>%s</HealthCheckId>"""

    XMLBody = """<ResourceRecordSet>
        <Name>%(name)s</Name>
        <Type>%(type)s</Type>
        %(weight)s
        %(body)s
        %(health_check)s
    </ResourceRecordSet>"""

    WRRBody = """
        <SetIdentifier>%(identifier)s</SetIdentifier>
        <Weight>%(weight)s</Weight>
    """

    RRRBody = """
        <SetIdentifier>%(identifier)s</SetIdentifier>
        <Region>%(region)s</Region>
    """

    FailoverBody = """
        <SetIdentifier>%(identifier)s</SetIdentifier>
        <Failover>%(failover)s</Failover>
    """

    ResourceRecordsBody = """
        <TTL>%(ttl)s</TTL>
        <ResourceRecords>
            %(records)s
        </ResourceRecords>"""

    ResourceRecordBody = """<ResourceRecord>
        <Value>%s</Value>
    </ResourceRecord>"""

    AliasBody = """<AliasTarget>
        <HostedZoneId>%(hosted_zone_id)s</HostedZoneId>
        <DNSName>%(dns_name)s</DNSName>
        %(eval_target_health)s
    </AliasTarget>"""

    EvaluateTargetHealth = """<EvaluateTargetHealth>%s</EvaluateTargetHealth>"""

    valid_failover_roles = ['PRIMARY', 'SECONDARY']

    def __init__(self, name=None, type=None, ttl=600, resource_records=None,
            alias_hosted_zone_id=None, alias_dns_name=None, identifier=None,
            weight=None, region=None, alias_evaluate_target_health=None,
            health_check=None, failover_role=None):
        self.name = name
        self.type = type
        self.ttl = ttl
        if resource_records is None:
            resource_records = []
        self.resource_records = resource_records
        self.alias_hosted_zone_id = alias_hosted_zone_id
        self.alias_dns_name = alias_dns_name
        self.identifier = identifier
        self.weight = weight
        self.region = region
        self.alias_evaluate_target_health = alias_evaluate_target_health
        self.health_check = health_check
        self.failover_role = None
        if failover_role in self.valid_failover_roles or failover_role is None:
            self.failover_role = failover_role
        else:
            raise AttributeError(
                "Valid values for failover_role are: %s" %
                ",".join(self.valid_failover_roles))

    def __repr__(self):
        return '<Record:%s:%s:%s>' % (self.name, self.type, self.to_print())

    def add_value(self, value):
        """Add a resource record value"""
        self.resource_records.append(value)

    def set_alias(self, alias_hosted_zone_id, alias_dns_name,
                  alias_evaluate_target_health=False):
        """Make this an alias resource record set"""
        self.alias_hosted_zone_id = alias_hosted_zone_id
        self.alias_dns_name = alias_dns_name
        self.alias_evaluate_target_health = alias_evaluate_target_health

    def to_xml(self):
        """Spit this resource record set out as XML"""
        if self.alias_hosted_zone_id is not None and self.alias_dns_name is not None:
            # Use alias
            if self.alias_evaluate_target_health is not None:
                eval_target_health = self.EvaluateTargetHealth % ('true' if self.alias_evaluate_target_health else 'false')
            else:
                eval_target_health = ""

            body = self.AliasBody % { "hosted_zone_id": self.alias_hosted_zone_id,
                                      "dns_name": self.alias_dns_name,
                                      "eval_target_health": eval_target_health }
        else:
            # Use resource record(s)
            records = ""

            for r in self.resource_records:
                records += self.ResourceRecordBody % r

            body = self.ResourceRecordsBody % {
                "ttl": self.ttl,
                "records": records,
            }

        weight = ""

        if self.identifier is not None and self.weight is not None:
            weight = self.WRRBody % {"identifier": self.identifier, "weight":
                    self.weight}
        elif self.identifier is not None and self.region is not None:
            weight = self.RRRBody % {"identifier": self.identifier, "region":
                    self.region}
        elif self.identifier is not None and self.failover_role is not None:
            weight = self.FailoverBody % {"identifier": self.identifier, "failover":
                    self.failover_role}

        health_check = ""
        if self.health_check is not None:
            health_check = self.HealthCheckBody % (self.health_check)

        params = {
            "name": self.name,
            "type": self.type,
            "weight": weight,
            "body": body,
            "health_check": health_check
        }
        return self.XMLBody % params

    def to_print(self):
        rr = ""
        if self.alias_hosted_zone_id is not None and self.alias_dns_name is not None:
            # Show alias
            rr = 'ALIAS ' + self.alias_hosted_zone_id + ' ' + self.alias_dns_name
            if self.alias_evaluate_target_health is not None:
                rr += ' (EvalTarget %s)' % self.alias_evaluate_target_health
        else:
            # Show resource record(s)
            rr =  ",".join(self.resource_records)

        if self.identifier is not None and self.weight is not None:
            rr += ' (WRR id=%s, w=%s)' % (self.identifier, self.weight)
        elif self.identifier is not None and self.region is not None:
            rr += ' (LBR id=%s, region=%s)' % (self.identifier, self.region)

        return rr

    # this is a terrible thing to have to do, but I had to monkeypatch this to get it to work until new version of boto
    # comes out that addresses the missing health_check field addressed in this pull request
    # https://github.com/jzbruno/boto/commit/075634f49441ff293e1717d44c04862b257f65c6
    def endElement(self, name, value, connection):
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
        # following 2 add support for parsing health check id
        elif name == 'HealthCheckId':
            self.health_check = value
        # following 2 lines add support for parsing the failover role
        elif name == 'Failover':
            self.failover_role = value

    def startElement(self, name, attrs, connection):
        return None


class Route53Manager(BaseManager):

    def __get_boto_conn(self):
        if 'rout53' not in self.boto_conns:
            self.boto_conns["route53"] = boto.connect_route53(aws_access_key_id=self.settings.AWS_ACCESS_KEY, aws_secret_access_key=self.settings.AWS_SECRET_KEY)
            ################-------------START MONKEYPATCH-------------#####################
            # this is a terrible thing to have to do, but I had to monkeypatch this to get it to work until boto supports the needed functionality
            # related pull requests:
            # https://github.com/boto/boto/pull/2195
            # https://github.com/boto/boto/pull/2222

            boto.route53.record.Record = Record
            ################-------------END MONKEYPATCH-------------#####################
        return self.boto_conns["route53"]


    #TODO implement interactive mode
    #TODO need to figure out how to handle a host in multiple zones (possible: preferred zone, and handling in interactive)
    def discovery(self, prefer_hostname='external', interactive=False, load_route53_only=False):
        botoconn = self.__get_boto_conn()
        health_checks = botoconn.get_list_health_checks()
        ids = []
        for health_check in health_checks['ListHealthChecksResponse']['HealthChecks']:
            hcid = self.store_healthcheck(health_check)
            if hcid:
                ids.append(hcid)

        #remove healthchecks that no longer exist in route53
        if len(ids):
            self.db.execute("delete from route53_healthchecks where id not in " + " ({0})".format(",".join("{0}".format(n) for n in ids)))
            self.dbconn.commit()

        zonesdata = botoconn.get_all_hosted_zones()
        for zd in zonesdata['ListHostedZonesResponse']['HostedZones']:
            comment = None
            if "Comment" in zd['Config']:
                comment = zd['Config']['Comment']
            # strip the trailing '.' on the zone name
            zone_name = zd['Name']
            if zone_name[len(zone_name)-1] == '.':
                zone_name = zone_name[0:len(zone_name)-1]

            self.db.execute("replace into route53_zones set zone_id=%s, name=%s, record_sets=%s, comment=%s", (zd['Id'].replace('/hostedzone/',''), zone_name, zd['ResourceRecordSetCount'], comment))
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
            #   latency will include a value for region, and failover will not include weight or region #TODO verify assumption on failover type
            for r in recs:
                name = r.name
                #TODO need to find out if i could ever get relative hostnames (rather than fqdn) back from this API call
                if name[len(name)-1] == '.':
                    name = name[0:len(name)-1]
                ident = r.identifier
                if not r.identifier:
                    ident = ""
                self.db.execute("insert into route53_records set zone_id=%s, name=%s, type=%s, identifier=%s, resource_records=%s, ttl=%s, alias_hosted_zone_id=%s, "
                                "alias_dns_name=%s, weight=%s, region=%s, healthcheck_id=%s on duplicate key update resource_records=%s, ttl=%s, alias_hosted_zone_id=%s, "
                                "alias_dns_name=%s, weight=%s, region=%s, healthcheck_id=%s",
                                (zone_id, name, r.type, ident, "\n".join(r.resource_records), r.ttl, r.alias_hosted_zone_id, r.alias_dns_name, r.weight, r.region, r.health_check,
                                "\n".join(r.resource_records), r.ttl, r.alias_hosted_zone_id, r.alias_dns_name, r.weight, r.region, r.health_check))
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
                if hostname and hostname != host[1]:
                    self.logger.info("Found hostname for instance {0}, updating from {1} to {2}".format(host[0], host[1], hostname))
                    self.db.execute("update hosts set host=%s where instance_id=%s", (hostname, host[0]))
                    self.dbconn.commit()


    def store_healthcheck(self, health_check):
        resource_path = None
        if 'ResourcePath' in health_check['HealthCheckConfig']:
            resource_path = health_check['HealthCheckConfig']['ResourcePath']
        search_string = None
        if 'SearchString' in health_check['HealthCheckConfig']:
            search_string = health_check['HealthCheckConfig']['SearchString']
        fqdn = None
        if 'FullyQualifiedDomainName' in health_check['HealthCheckConfig']:
            fqdn = health_check['HealthCheckConfig']['FullyQualifiedDomainName']
        ipaddr = None
        if 'IPAddress' in health_check['HealthCheckConfig']:
            ipaddr = health_check['HealthCheckConfig']['IPAddress']

        self.logger.info("Storing health check: {0}://{1}:{2}".format(health_check['HealthCheckConfig']['Type'], ipaddr, health_check['HealthCheckConfig']['Port']))
        self.db.execute("insert into route53_healthchecks set healthcheck_id=%s, ip=%s, port=%s, type=%s, request_interval=%s, "
                        "failure_threshold=%s, resource_path=%s, search_string=%s, fqdn=%s, caller_reference=%s "
                        "on duplicate key update ip=%s, port=%s, type=%s, request_interval=%s, failure_threshold=%s, "
                        "resource_path=%s, search_string=%s, fqdn=%s, caller_reference=%s",
                        (health_check['Id'], ipaddr, health_check['HealthCheckConfig']['Port'],
                         health_check['HealthCheckConfig']['Type'], health_check['HealthCheckConfig']['RequestInterval'],
                         health_check['HealthCheckConfig']['FailureThreshold'], resource_path, search_string, fqdn, health_check['CallerReference'],
                         ipaddr, health_check['HealthCheckConfig']['Port'], health_check['HealthCheckConfig']['Type'],
                         health_check['HealthCheckConfig']['RequestInterval'], health_check['HealthCheckConfig']['FailureThreshold'],
                         resource_path, search_string, fqdn, health_check['CallerReference']))
        self.dbconn.commit()
        self.db.execute("select id from route53_healthchecks where healthcheck_id=%s", (health_check['Id'], ))
        row = self.db.fetchone()
        if not row:
            return None
        else:
            return row[0]


    def create_health_check(self, ip, port, protocol, request_interval=30, failure_threshold=3, resource_path=None, fqdn=None, string_match=None):
        botoconn = self.__get_boto_conn()
        hc_type = None
        if protocol == 'tcp':
            hc_type = 'TCP'
        elif protocol == 'http':
            hc_type = 'HTTP'
        elif protocol == 'https':
            hc_type = 'HTTPS'

        if not hc_type:
            raise AttributeError("Protocol must be one of [tcp, http, https]")
        if not ip:
            raise AttributeError("ip must be provided for healthcheck")
        if not port:
            raise AttributeError("port must be provided for healthcheck")

        if string_match and hc_type in ('HTTP', 'HTTPS'):
            hc_type += '_STR_MATCH'

        hc = HealthCheck(ip, port, hc_type, resource_path, fqdn, string_match, request_interval, failure_threshold)
        self.logger.debug(hc)
        response = botoconn.create_health_check(hc)
        #TODO need to find out what an error response looks like
        hcid = None
        if 'CreateHealthCheckResponse' in response:
            if 'HealthCheck' in response['CreateHealthCheckResponse']:
                hcid = self.store_healthcheck(response['CreateHealthCheckResponse']['HealthCheck'])

        if hcid:
            conf = response['CreateHealthCheckResponse']['HealthCheck']['HealthCheckConfig']
            self.logger.info("Created healthcheck {0}: {1}://{2}:{3}".format(hcid, conf['Type'], conf['IPAddress'], conf['Port']))

        return hcid

    def create_dns_record(self, fqdn, record_type, zone_id, records, ttl=60, routing_policy='simple', weight=None, identifier=None, region=None, health_check_id=None, failover_role="primary"):
        botoconn = self.__get_boto_conn()
        if routing_policy == 'simple':
            weight = None
            identifier = None
            region = None
            health_check_id = None
            failover_role = None
        elif routing_policy == 'weighted':
            region = None
            failover_role = None
            if not weight:
                raise AttributeError("weight must be provided for weighted routing policy")
            if not identifier:
                raise AttributeError("identifier must be provided for weighted routing policy")
        elif routing_policy == 'latency':
            weight = None
            failover_role = None
            if not region:
                raise AttributeError("region must be provided for latency routing policy")
            if not identifier:
                raise AttributeError("identifier must be provided for latency routing policy")
        elif routing_policy == 'failover':
            weight = None
            region = None
            if not failover_role:
                raise AttributeError("failover_role must be provided for failover routing policy")
            if not identifier:
                raise AttributeError("identifier must be provided for failover routing policy")

        health_check = None
        if health_check_id:
            self.db.execute("select healthcheck_id from route53_healthchecks where id=%s", (health_check_id, ))
            row = self.db.fetchone()
            if not row:
                raise ResourceNotFound("Could not find information on health check {0}".format(health_check_id))
            health_check = row[0]

        zones = botoconn.get_zones()
        zone = None
        # unfortunately boto's get_zone only takes a zone name which is not necessarily unique :(
        for z in zones:
            if z.id == zone_id:
                zone = z
                break
        if not zone:
            raise ResourceNotFound("Zone ID {0} not found".format(zone_id))

        rrset = zone.get_records()
        record_type = record_type.upper()
        if failover_role is not None:
            failover_role = failover_role.upper()
        rec = Record(name=fqdn, type=record_type, ttl=ttl, resource_records=records, identifier=identifier, weight=weight, region=region, health_check=health_check, failover_role=failover_role)
        rrset.add_change_record('CREATE', rec)
        response = rrset.commit()

        if 'ChangeResourceRecordSetsResponse' in response:
            name = rec.name
            if name[len(name)-1] == '.':
                name = name[0:len(name)-1]
            ident = rec.identifier
            if not rec.identifier:
                ident = ""
            self.db.execute("insert into route53_records set zone_id=%s, name=%s, type=%s, identifier=%s, resource_records=%s, ttl=%s, alias_hosted_zone_id=%s, "
                            "alias_dns_name=%s, weight=%s, region=%s, healthcheck_id=%s on duplicate key update resource_records=%s, ttl=%s, alias_hosted_zone_id=%s, "
                            "alias_dns_name=%s, weight=%s, region=%s, healthcheck_id=%s",
                            (zone_id, name, rec.type, ident, "\n".join(rec.resource_records), rec.ttl, rec.alias_hosted_zone_id, rec.alias_dns_name, rec.weight, rec.region, rec.health_check,
                             "\n".join(rec.resource_records), rec.ttl, rec.alias_hosted_zone_id, rec.alias_dns_name, rec.weight, rec.region, rec.health_check))
            self.dbconn.commit()
            self.logger.info("Created new dns entry for {0} -> {1}".format(fqdn, " \\n ".join(records)))
            self.db.execute("update route53_zones z set record_sets = (select count(*) from route53_records where zone_id=z.zone_id)")
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

    def delete_dns_record(self, zone_id, fqdn, record_type, identifier=None):
        # normalize values
        record_type = record_type.upper()
        fqdn = fqdn.lower()
        if fqdn[len(fqdn)-1] != '.':
            fqdn += '.'

        botoconn = self.__get_boto_conn()

        zones = botoconn.get_zones()
        zone = None
        # unfortunately boto's get_zone only takes a zone name which is not necessarily unique :(
        for z in zones:
            if z.id == zone_id:
                zone = z
                break
        if not zone:
            raise ResourceNotFound("Zone ID {0} not found".format(zone_id))

        rrset = zone.get_records()
        record = None
        for r in rrset:
            if r.name == fqdn and r.type == record_type and r.identifier == identifier:
                record = r
                break
        if not record:
            raise ResourceNotFound("Cannot find DNS record for {0} {1} {2} {3}", format(zone_id, fqdn, record_type, identifier))

        rrset.add_change_record('DELETE', record)

        # for some reason, a properly formed response is not being returned, but the record is deleted from route53
        # adding the response to the debug log for now to keep an eye on it
        response = rrset.commit()
        self.logger.debug(response)
        #if 'ChangeResourceRecordSetsResponse' in response:
        name = record.name
        if name[len(name)-1] == '.':
            name = name[0:len(name)-1]
        if not identifier:
            identifier = ""
        self.db.execute("delete from route53_records where zone_id=%s and name=%s and type=%s and identifier=%s", (zone_id, fqdn, record_type, identifier))
        self.dbconn.commit()
        self.logger.info("Deleted DNS record for {0} {1} {2} {3}".format(zone_id, fqdn, record_type, identifier))
        self.db.execute("update route53_zones z set record_sets = (select count(*) from route53_records where zone_id=z.zone_id)")
        self.dbconn.commit()

    def delete_healthcheck(self, healthcheck_id, force=False):
        self.db.execute("select h.healthcheck_id, r.healthcheck_id, r.name, r.zone_id from route53_healthchecks h left join route53_records r on h.healthcheck_id=r.healthcheck_id where id=%s", (healthcheck_id, ))
        row = self.db.fetchone()
        if not row:
            raise ResourceNotFound("Health check {0} not found".format(healthcheck_id))

        if row[1] is not None and not force:
            raise ResourceNotAvailable("Health check {0} is currently in use for a dns entry in zone {1} with FQDN of {2}".format(healthcheck_id, row[3], row[2]))

        botoconn = self.__get_boto_conn()
        response = botoconn.delete_health_check(row[0])

        if 'DeleteHealthCheckResponse' in response:
            self.db.execute("delete from route53_healthchecks where id=%s", (healthcheck_id, ))
            self.dbconn.commit()
            self.logger.info("Deleted health check {0} ({1})".format(healthcheck_id, row[0]))


    def argument_parser_builder(self, parser):
        rsubparser = parser.add_subparsers(title="action", dest='action')

        # ams route53 discovery
        discparser = rsubparser.add_parser("discovery", help="Run discovery on route53 to populate database with DNS data")
        discparser.add_argument("--interactive", help="Enable interactive mode for applying discovered host names to hosts (not enabled yet)", action='store_true')
        discparser.add_argument("--prefer", default='external', choices=['internal', 'external'], help="Sets which hostname gets preference if DNS records are defined for an internal address and an external address")
        discparser.add_argument("--load-only", help="Only load the route53 tables, but do not apply hostname changes to hosts", action='store_true')
        discparser.set_defaults(func=self.command_discover)

        listparser = rsubparser.add_parser("list", help="List Route53 DNS information currently in the database")
        listparser.add_argument("resource", nargs='?', default="dns", choices=["dns", "healthchecks", "zones"], help="Resource type to list")
        listparser.set_defaults(func=self.command_list)

        adddnssharedargs = argparse.ArgumentParser(add_help=False)
        adddnssharedargs.add_argument('fqdn', help="Fully qualified domain name for the entry. You can include the trailing dot(.) or it will be added automatically")
        adddnssharedargs.add_argument('record_type', help="DNS record type (currently only support A and CNAME)", choices=['A', 'CNAME'])
        group = adddnssharedargs.add_mutually_exclusive_group(required=True)
        group.add_argument('--zone-id', help="Zone id to add DNS record to")
        group.add_argument('--zone-name', help="Zone name to add DNS record to")
        adddnssharedargs.add_argument('-t', '--ttl', help="TTL for the entry (default: 60)", type=int, default=60)
        adddnssharedargs.add_argument('-r', '--routing-policy', help='The routing policy to use (default: simple)', choices=['simple', 'weighted', 'latency', 'failover'], default='simple')
        adddnssharedargs.add_argument('-w', '--weight', type=int, help="Weighted routing policy: weight to assign to the dns resource")
        adddnssharedargs.add_argument('--region', help="Latency routing policy: assigns the region for the dns resource for routing")
        adddnssharedargs.add_argument('--health-check', type=int, help="health check id to associate with the record (for IDs, use: ams route53 list healthchecks)")
        adddnssharedargs.add_argument('--failover-role', help="Failover routing policy: defines whether resource is primary or secondary", choices=['primary','secondary'], default='primary')

        # ams route53 dns
        dnsparser = rsubparser.add_parser("dns", help="DNS management operations")
        dnssubparser = dnsparser.add_subparsers(title="operation", dest="operation")

        # ams route53 dns create
        creatednsparser = dnssubparser.add_parser("create", help="Create new DNS entry", parents=[adddnssharedargs])
        creatednsparser.add_argument('-v', '--record-value', help="Value for the DNS record (Currently only has support single value entries)", required=True)
        creatednsparser.add_argument('--identifier', help="Unique identifier to associate to a record that shares a name/type with other records in weighted, latency, or failover records")
        creatednsparser.set_defaults(func=self.command_create_dns)

        # ams route53 dns add
        adddnsparser = dnssubparser.add_parser("add", help="add dns entries for host/instance", parents=[adddnssharedargs])
        group = adddnsparser.add_mutually_exclusive_group(required=True)
        group.add_argument('-H', '--host', help="Hostname (to find current hostname use: ams host list)")
        group.add_argument('-i', '--instance', help="Instance ID")
        adddnsparser.add_argument('--use', help="Define whether to use the public or private hostname/IP", choices=["public", "private"], default="public")
        adddnsparser.add_argument('--identifier', help="Unique identifier to associate to a record that shares a name/type with other records in weighted, latency, or failover records. If not provided, one will be created from the hostname or instance id")
        adddnsparser.add_argument('--update-hosts', action='store_true', help="(routing_policy=simple only) Updates the hostname for the host in the AMS hosts table (saving you from having to run route53 discovery to update)")
        adddnsparser.add_argument('--configure-hostname', action='store_true', help="(routing_policy=simple only) Set the hostname on the host to the FQDN that was just added to the host or the currently set uname (uname will override the FQDN). Also applies the --update-hosts option (for Ubuntu and Redhat flavors, it will also edit the proper files to make this change permanent)")
        group = adddnsparser.add_argument_group(title="Health Check Options", description="Use these options to create a health check for the dns record being added to host")
        group.add_argument('--hc', action='store_true', help="Create a Route53 health check for host")
        group.add_argument('--hc-port', type=int, help="Health check port")
        group.add_argument('--hc-type', help="Health check type", choices=['tcp', 'http', 'https'])
        group.add_argument('--hc-interval', type=int, help="Health check interval (10 or 30 second)", choices=[10,30], default=30)
        group.add_argument('--hc-threshold', type=int, help="Number of times health check fails before the host is marked down by Route53", choices=range(1, 11), default=3)
        group.add_argument('--hc-path', help="HTTP/HTTPS: health check resource path")
        group.add_argument('--hc-fqdn', help="HTTP/HTTPS: health check fully qualified domain name")
        group.add_argument('--hc-match', help="HTTP/HTTPS: health check response match string")
        group.add_argument('--hc-ip', help="IP address to use for the healthcheck. Default is to use the instance's external IP, but this argument can be used to override")
        adddnsparser.set_defaults(func=self.command_add_dns)

        # ams route53 dns update
        updatednsparser = dnssubparser.add_parser("update", help="Update a DNS entry")
        updatednsparser.set_defaults(func=self.command_not_implemented)
        # ams route53 dns delete
        deletednsparser = dnssubparser.add_parser("delete", help="Delete a DNS entry")
        deletednsparser.set_defaults(func=self.command_delete_dns)
        deletednsparser.add_argument('fqdn', help="Fully qualified domain name for the entry. You can include the trailing dot(.) or it will be added automatically")
        deletednsparser.add_argument('record_type', help="DNS record type (currently only support A and CNAME)", choices=['A', 'CNAME'])
        deletednsparser.add_argument('--identifier', help="Unique identifier for a record that shares a name/type with other records in weighted, latency, or failover records")
        group = deletednsparser.add_mutually_exclusive_group(required=True)
        group.add_argument('--zone-id', help="Zone id to add DNS record to")
        group.add_argument('--zone-name', help="Zone name to add DNS record to")


        # ams route53 healthchecks
        healthparser = rsubparser.add_parser("healthcheck", help="Route53 healthcheck management operations")
        healthsubparser = healthparser.add_subparsers(title="operation", dest="operation")

        # ams route53 healthchecks create
        createhealthparser = healthsubparser.add_parser("create", help="Create a new health check")
        createhealthparser.add_argument('ip', help='IP address to health check')
        createhealthparser.add_argument('port', type=int, help="Health check port")
        createhealthparser.add_argument('type', help="Health check type", choices=['tcp', 'http', 'https'])
        createhealthparser.add_argument('-i', '--interval', type=int, help="Health check interval (10 or 30 second)", choices=[10,30], default=30)
        createhealthparser.add_argument('-f', '--failure-threshold', type=int, help="Number of times health check fails before the host is marked down by Route53", choices=range(1, 11), default=3)
        createhealthparser.add_argument('-a', '--resource-path', help="HTTP/HTTPS: health check resource path")
        createhealthparser.add_argument('-d', '--fqdn', help="HTTP/HTTPS: health check fully qualified domain name")
        createhealthparser.add_argument('-s', '--string-match', help="HTTP/HTTPS: health check response match string")
        createhealthparser.set_defaults(func=self.command_create_healthcheck)

        # ams route53 healthchecks update
        updatehealthparser = healthsubparser.add_parser("update", help="Update a health check")
        updatehealthparser.set_defaults(func=self.command_not_implemented)
        # ams route53 healthchecks delete
        deletehealthparser = healthsubparser.add_parser("delete", help="Delete a health check")
        deletehealthparser.add_argument('healthcheck_id', type=int, help='ID of the health check to delete. To list health check ID run: ams route53 list healthchecks')
        deletehealthparser.add_argument('--force', action='store_true', help="Force the deletion of a health check even if it is still defined as the health check for a record")
        deletehealthparser.set_defaults(func=self.command_delete_healthcheck)

    def command_delete_healthcheck(self, args):
        self.delete_healthcheck(args.healthcheck_id, args.force)

    def command_delete_dns(self, args):
        zone_id = None
        zone_name = None
        if args.zone_id:
            whereclause = 'zone_id=%s'
            wherevar = args.zone_id
        if args.zone_name:
            whereclause = 'name=%s'
            wherevar = args.zone_name
        self.db.execute("select zone_id, name from route53_zones where " + whereclause, (wherevar, ))
        rows = self.db.fetchall()
        if not rows:
            self.logger.error("No Route53 zone ID found")
            return
        elif len(rows) > 1:
            self.logger.error("Multiple zones found for zone name: {0}. Use --zone-id instead".format(args.zone_name))
            return
        else:
            zone_name = rows[0][1]
            zone_id = rows[0][0]
        self.delete_dns_record(zone_id=zone_id, fqdn=args.fqdn, record_type=args.record_type, identifier=args.identifier)

    def command_add_dns(self, args):
        if args.host:
            whereclause = "host=%s"
            wherevar = args.host
        elif args.instance:
            whereclause = "instance_id=%s"
            wherevar = args.instance

        self.db.execute("select instance_id, host, hostname_internal, hostname_external, ip_internal, ip_external, availability_zone from hosts where `terminated`=0 and " + whereclause, (wherevar, ))
        row = self.db.fetchone()
        if not row:
            self.logger.error("{0} not found".format(wherevar))
            return
        instance_id = row[0]
        if args.use == 'public':
            cname_entry = row[3]
            ip_entry = row[5]
        elif args.use == 'private':
            cname_entry = row[2]
            ip_entry = row[4]

        if args.record_type == 'A':
            entry_value = ip_entry
            if not entry_value:
                self.logger.error("No {0} ip address on instance to use for A record".format(args.use))
                return
        elif args.record_type == 'CNAME':
            entry_value = cname_entry
            if not entry_value:
                self.logger.error("No {0} dns name on instance to use for CNAME record".format(args.use))
                return

        healthcheck_id = None
        if args.hc:
            hcip = None
            if row[5]:
                hcip = row[5]
            if args.hc_ip:
                hcip = args.hc_ip

            if not hcip:
                self.logger.error("Instance does not have a public IP address and there was no healthcheck IP override given")
                return

            healthcheck_id = self.create_health_check(ip=hcip, port=args.hc_port, protocol=args.hc_type, request_interval=args.hc_interval, failure_threshold=args.hc_threshold, resource_path=args.hc_path, fqdn=args.hc_fqdn, string_match=args.hc_match)
            if not healthcheck_id:
                self.logger.error("Unknown error creating health check")
                return
            self.logger.info("Created new health check with id: {0}".format(healthcheck_id))

        if not args.identifier and args.routing_policy in ('weighted', 'latency', 'failover'):
            # will use public dns, public ip, private dns, private (in that order of precedence) for the unique identifier if it is needed and not provided
            if row[3]:
                args.identifier = row[3]
            elif row[5]:
                args.identifier = row[5]
            elif row[2]:
                args.identifier = row[2]
            elif row[4]:
                args.identifier = row[4]

        if args.routing_policy == 'latency' and not args.region:
            args.region = self.parse_region_from_availability_zone(row[6])

        if healthcheck_id:
            args.health_check = healthcheck_id

        args.record_value = entry_value

        self.command_create_dns(args)

        if (args.configure_hostname or args.update_hosts) and args.routing_policy == 'simple':
            if args.configure_hostname:
                self.logger.info("Waiting 30 seconds to give route53 time to reflect the new dns changes")
                time.sleep(30)

            im = InstanceManager(self.settings)
            im.configure_hostname(instance_id, args.fqdn, args.configure_hostname)


    def command_create_healthcheck(self, args):
        self.create_health_check(ip=args.ip, port=args.port, protocol=args.type, request_interval=args.interval, failure_threshold=args.failure_threshold, resource_path=args.resource_path, fqdn=args.fqdn, string_match=args.string_match)

    def command_create_dns(self, args):
        zone_id = None
        zone_name = None
        if args.zone_id:
            whereclause = 'zone_id=%s'
            wherevar = args.zone_id
        if args.zone_name:
            whereclause = 'name=%s'
            wherevar = args.zone_name
        self.db.execute("select zone_id, name from route53_zones where " + whereclause, (wherevar, ))
        rows = self.db.fetchall()
        if not rows:
            self.logger.error("No Route53 zone ID found")
            return
        elif len(rows) > 1:
            self.logger.error("Multiple zones found for zone name: {0}. Use --zone-id instead".format(args.zone_name))
            return
        else:
            zone_name = rows[0][1]
            zone_id = rows[0][0]

        # normalize the fqdn
        fqdn = args.fqdn
        if fqdn[len(fqdn)-1] != '.':
            fqdn += '.'

        #TODO should likely put a check here to make sure that the fqdn is valid for the zone name
        self.create_dns_record(fqdn=fqdn, record_type=args.record_type, zone_id=zone_id, records=[args.record_value], ttl=args.ttl, routing_policy=args.routing_policy, weight=args.weight, identifier=args.identifier, region=args.region, health_check_id=args.health_check, failover_role=args.failover_role.upper())


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

        elif args.resource == "zones":
            self.db.execute("select zone_id, name, record_sets, comment from route53_zones")
            rows = self.db.fetchall()
            headers = ['zone id', 'zone name', 'records', 'comment']
            self.output_formatted("Route53 Zones", headers, rows)


