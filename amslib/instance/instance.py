import boto.ec2
import argparse
from amslib.core.manager import BaseManager
from amslib.ssh.sshmanager import SSHManager
from errors import *
import time
from pprint import pprint

# borrowed from http://stackoverflow.com/questions/4375327/python-argparse-preformatted-help-text
#TODO this should probably go somewhere central so that it can be used by other modules if needed
class SmartFormatter(argparse.HelpFormatter):

    def _split_lines(self, text, width):
        # this is the RawTextHelpFormatter._split_lines
        if text.startswith('R|'):
            return text[2:].splitlines()
        return argparse.HelpFormatter._split_lines(self, text, width)

class InstanceManager(BaseManager):

    def __get_boto_conn(self, region):
        if region not in self.boto_conns:
            self.boto_conns[region] = boto.ec2.connect_to_region(region, aws_access_key_id=self.settings.AWS_ACCESS_KEY, aws_secret_access_key=self.settings.AWS_SECRET_KEY)
        return self.boto_conns[region]

    def discover(self, get_unames = False):
        regions = boto.ec2.regions()
        instance_ids = []
        self.db.execute("update availability_zones set active=0")
        self.dbconn.commit()
        for region in regions:
            self.logger.info("Processing region {0}".format(region.name))
            botoconn = self.__get_boto_conn(region.name)
            try:
                zones = botoconn.get_all_zones()
                for zone in zones:
                    self.db.execute("insert into availability_zones set availability_zone=%s, region=%s, active=1 on duplicate key update active=1", (zone.name, region.name))
                    self.dbconn.commit()
            except:
                pass
            self.logger.info("Getting instances")
            try:
                instances = botoconn.get_only_instances()
            except boto.exception.EC2ResponseError:
                continue
            for i in instances:
                instance_ids.append(i.id)
                self.logger.info("Found instance {0}".format(i.id))
                name = None
                if 'Name' in i.tags:
                    name = i.tags['Name']
                hint = None
                hext = None
                hn = None
                if i.private_dns_name:
                    hint = i.private_dns_name
                if i.public_dns_name:
                    hext = i.public_dns_name
                if i.dns_name:
                    hn = i.dns_name

                uname = None
                if get_unames:
                    # TODO implement the ssh call to the host to gather the uname
                    pass

                self.db.execute("insert into hosts set instance_id=%s, host=%s, hostname_internal=%s, hostname_external=%s, "
                                "ip_internal=%s, ip_external=%s, ami_id=%s, instance_type=%s, availability_zone=%s, name=%s, uname=%s, vpc_id=%s, "
                                "subnet_id=%s on duplicate key update hostname_internal=%s, hostname_external=%s, ip_internal=%s, ip_external=%s, ami_id=%s, "
                                "instance_type=%s, availability_zone=%s, name=%s, host=COALESCE(host, %s), vpc_id=%s, subnet_id=%s", (i.id, hn, hint, hext,
                                                                            i.private_ip_address, i.ip_address, i.image_id, i.instance_type,
                                                                            i.placement, name, uname, i.vpc_id, i.subnet_id, hint, hext, i.private_ip_address,
                                                                            i.ip_address, i.image_id, i.instance_type, i.placement, name, hn, i.vpc_id, i.subnet_id))
                self.dbconn.commit()
                self.store_ec2_tags(i)

        self.db.execute("update hosts set `terminated`=0 where instance_id in ('{0}')".format("','".join(instance_ids)))
        self.dbconn.commit()
        self.db.execute("update hosts set `terminated`=1 where instance_id not in ('{0}')".format("','".join(instance_ids)))
        self.dbconn.commit()

    def store_ec2_tags(self, boto_instance):
        self.db.execute("update tags set removed=1 where resource_id=%s and `type`='standard' ", (boto_instance.id, ))
        self.dbconn.commit()
        for tagname in boto_instance.tags:
            tagval = boto_instance.tags[tagname]
            self.logger.debug("Updating tag database for tag {0} to value {1} for instance {2}".format(tagname, tagval, boto_instance.id))
            self.db.execute("insert into tags set resource_id=%s, name=%s, value=%s, removed=0 on duplicate key update value=%s, removed=0", (boto_instance.id, tagname, tagval, tagval))
            self.dbconn.commit()
        self.db.execute("delete from tags where resource_id=%s and removed=1", (boto_instance.id, ))
        self.dbconn.commit()



    def add_tag(self, instance_id, tagname, tagvalue, tagtype='standard'):
        region, availability_zone, instance = self._get_instance_info(instance_id)
        self.logger.info("Adding {0} tag {1} with value {2} to instance {3} in {4}".format(tagtype, tagname, tagvalue, instance_id, availability_zone))
        if tagtype == 'standard':
            try:
                instance.add_tag(tagname, tagvalue)
            except boto.exception.EC2ResponseError as e:
                if e.code == 'TagLimitExceeded':
                    self.logger.error("Unable to add tag to EC2 instance, tag limit already reached. Only extended tags can be used until some standard tags are removed from the instance.")
                    return
                else:
                    raise
        self.db.execute("insert into tags set resource_id=%s, name=%s, value=%s, type=%s, removed=0 on duplicate key update value=%s, removed=0", (instance_id, tagname, tagvalue, tagtype, tagvalue))
        self.dbconn.commit()


    def remove_tag(self, instance_id, tagname):
        region, availability_zone, instance = self._get_instance_info(instance_id)
        self.logger.info("Deleting tag {0} from instance {1} in {2}".format(tagname, instance_id, availability_zone))
        self.db.execute("select type from tags where resource_id=%s and name=%s", (instance_id, tagname))
        row = self.db.fetchone()
        if not row:
            self.logger.error("Tag {0} not found for instance {0}")
            return
        if row[0] == 'standard':
            instance.remove_tag(tagname)

        self.db.execute("delete from tags where resource_id=%s and name=%s", (instance_id, tagname))
        self.dbconn.commit()


    def _get_instance_info(self, instance_id):
        self.db.execute("SELECT availability_zone, host from hosts where instance_id=%s", (instance_id, ))
        data = self.db.fetchone()
        if not data:
            raise InstanceNotFound("Instance {0} not found; unable to lookup availability zone for instance, try running: ams host discovery".format(instance_id))
        availability_zone, host = data
        region = self.parse_region_from_availability_zone(availability_zone)
        botoconn = self.__get_boto_conn(region)
        instance = botoconn.get_only_instances([instance_id])[0]

        return region, availability_zone, instance


    def configure_hostname(self, instance_id, hostname, configure_server=False):
        self.db.execute("select instance_id, hostname_external, hostname_internal from hosts where host=%s",(hostname, ))
        rows = self.db.fetchall()
        # This updates any hosts with the hostname given to their external or internal hostname before applying that hostname to another host
        if rows:
            for row in rows:
                hn = None
                if row[2]:
                    hn = row[2]
                if row[1]:
                    hn = row[1]

                self.db.execute("update hosts set host=%s where instance_id=%s", (hn, row[0]))
                self.dbconn.commit()
        self.db.execute("update hosts set host=%s where instance_id=%s", (hostname, instance_id))
        self.dbconn.commit()

        self.db.execute("select instance_id, host, uname from hosts where instance_id=%s", (instance_id, ))
        row = self.db.fetchone()
        if not row:
            self.logger.error("Unable to find instance metadata")
            return

        # if there is a uname set then we will use that rather than the hostname to set the system uname
        uname = row[1]
        if row[2]:
            uname = row[2]

        sh = SSHManager(self.settings)
        sh.connect_instance(instance=instance_id, port=self.settings.SSH_PORT, username=self.settings.SSH_USER, password=self.settings.SSH_PASSWORD, key_filename=self.settings.SSH_KEYFILE)

        self.logger.info("Setting the running value for hostname on the instance")
        stdout, stderr, exit_code = sh.sudo('hostname {0}'.format(uname), sudo_password=self.settings.SUDO_PASSWORD)
        if int(exit_code) != 0:
            self.logger.error("There was an error setting the running hostname of the instance\n" + stderr)
            return

        permanent = False
        # Redhat/CentOS uses a "HOSTNAME=somehost.example.com" line in /etc/sysconfig/network to set hostname permanently
        stdout, stderr, exit_code = sh.sudo('cat /etc/sysconfig/network', sudo_password=self.settings.SUDO_PASSWORD)
        if int(exit_code) == 0:
            self.logger.info("/etc/sysconfig/network file found, modifying HOSTNAME")
            hoststring = "HOSTNAME={0}".format(uname)
            lines = stdout.strip().split("\n")
            found = False
            for i in range(0, len(lines)):
                if lines[i][0:8] == 'HOSTNAME':
                    lines[i] = hoststring
                    found = True
                    break
            if not found:
                lines.append(hoststring)

            sh.sudo('mv -f /etc/sysconfig/network /etc/sysconfig/network.prev', sudo_password=self.settings.SUDO_PASSWORD)
            for line in lines:
                sh.sudo('echo {0} >> /etc/sysconfig/network'.format(line), sudo_password=self.settings.SUDO_PASSWORD)
            permanent = True

        # Ubuntu uses "somehost.example.com" as the contents of /etc/hostname to set hostname permanently
        stdout, stderr, exit_code = sh.sudo('cat /etc/hostname', sudo_password=self.settings.SUDO_PASSWORD)
        if int(exit_code) == 0:
            self.logger.info("/etc/hostname file found, setting hostname")
            sh.sudo('cp /etc/hostname /etc/hostname.prev', sudo_password=self.settings.SUDO_PASSWORD)
            sh.sudo('echo {0} > /etc/hostname'.format(uname), sudo_password=self.settings.SUDO_PASSWORD)
            permanent = True

        if permanent:
            self.logger.info("Hostname configured permanently on instance")


    def argparse_stub(self):
        return 'host'


    def argparse_help_text(self):
        return 'direct host/instance related operations'


    def argument_parser_builder(self, parser):

        hsubparser = parser.add_subparsers(title="action", dest='action')

        # ams host list
        hlistparser = hsubparser.add_parser("list", help="list currently managed hosts")
        hlistparser.add_argument('search_field', nargs="?", help="field to search (host or instance_id)", choices=['host', 'instance_id', 'name'])
        hlistparser.add_argument('field_value', nargs="?", help="exact match search value")
        hlistparser.add_argument("--like", help="string to find within 'search-field'")
        hlistparser.add_argument("--prefix", help="string to prefix match against 'search-field'")
        hlistparser.add_argument("--zone", help="Availability zone to filter results by. This is a prefix search so any of the following is valid with increasing specificity: 'us', 'us-west', 'us-west-2', 'us-west-2a'")
        hlistparser.add_argument("-x", "--extended", help="Show extended information on hosts", action='store_true')
        hlistparser.add_argument("-a", "--all", help="Include terminated instances (that have been added via discovery)", action='store_true')
        hlistparser.add_argument("--terminated", help="Show only terminated instances (that have been added via discovery)", action='store_true')
        hlistparser.add_argument("-s", "--show-tags", help="Display tags for instances", action='store_true')
        hlistparser.set_defaults(func=self.command_host_list)

        addeditargs = argparse.ArgumentParser(add_help=False)
        addeditargs.add_argument('-i', '--instance', help="Instance ID of the instance to add", required=True)
        addeditargs.add_argument('-u', '--uname', help="Hostname to use when setting uname on the host (default is to use instance hostname)")
        addeditargs.add_argument('--hostname-internal', help="Internal hostname (stored but not currently used)")
        addeditargs.add_argument('--hostname-external', help="External hostname (stored but not currently used)")
        addeditargs.add_argument('--ip-internal', help="Internal IP address (stored but not currently used)")
        addeditargs.add_argument('--ip-external', help="External IP address (stored but not currently used)")
        addeditargs.add_argument('--ami-id', help="AMI ID (stored but not currently used)")
        addeditargs.add_argument('--instance-type', help="Instance type (stored but not currently used)")
        addeditargs.add_argument('--notes', help="Notes on the instance/host (stored but not currently used)")
        addeditargs.add_argument('--name', help="Name of the host (should match the 'Name' tag in EC2 for the instance)")

        # ams host add
        haddparser = hsubparser.add_parser("add", help="Add host to the database to be managed", parents=[addeditargs])
        haddparser.add_argument('-H', '--hostname', help="Hostname of the host (used to ssh to the host to do management)", required=True)
        haddparser.add_argument('-z', '--zone', help="availability zone that the instance is in", required=True)
        haddparser.set_defaults(func=self.command_host_add)

        # ams host edit
        heditparser = hsubparser.add_parser("edit", help="Edit host details in the database. Values can be passed as an empty string ('') to nullify them", parents=[addeditargs])
        heditparser.add_argument('-H', '--hostname', help="Hostname of the host (used to ssh to the host to do management)")
        heditparser.add_argument('--configure-hostname', action='store_true', help="Set the hostname on the host to the FQDN that is currently the hostname or the uname that is currently defined for the instance in AMS (uname will override FQDN)")
        heditparser.add_argument('-z', '--zone', help="Availability zone that the instance is in")
        heditparser.set_defaults(func=self.command_host_edit)

        discparser = hsubparser.add_parser("discovery", help="Run discovery on hosts/instances to populate database with resources")
        discparser.add_argument("--get-unames", action='store_true', help="Connects to each server to query the system's uname, much slower discovery due to ssh to each host (not implemented yet)")
        discparser.set_defaults(func=self.command_discover)


        htagargs = argparse.ArgumentParser(add_help=False)
        htagargs.add_argument('--prefix', help="For host/name identification, treats the given string as a prefix", action='store_true')
        htagargs.add_argument('--like', help="For host/name identification, searches for instances that contain the given string", action='store_true')
        htagargs.add_argument('-t', '--tag', help="R|Filter instances by tag, in the form name<OPERATOR>value.\nValid operators: \n\t=\t(equal)\n\t!=\t(not equal)\n\t=~\t(contains/like)\n\t!=~\t(not contains/not like)\n\t=:\t(prefixed by)\n\t!=:\t(not prefixed by)\nEg. To match Name tag containing 'foo': --tag Name=~foo", action='append')
        htaggroup = htagargs.add_mutually_exclusive_group()
        htaggroup.add_argument('-i', '--instance', help="instance_id of an instance to manage tags")
        htaggroup.add_argument('-H', '--host', help="hostname of an instance to manage tags")
        htaggroup.add_argument('-e', '--name', help="name of an instance to manage tags")

        # ams host tag
        htagparser = hsubparser.add_parser("tag", help="Manage tags for instances")
        htagsubparser = htagparser.add_subparsers(title="operation", dest='operation')

        # ams host tag list
        htaglist = htagsubparser.add_parser('list', help="List instance tags", parents=[htagargs], formatter_class=SmartFormatter)
        htaglist.set_defaults(func=self.command_tag)

        # ams host tag add
        htagadd = htagsubparser.add_parser('add', help="Add tag to an instance or group of instances", parents=[htagargs], formatter_class=SmartFormatter)
        htagadd.add_argument('tagname', help="Name of the tag")
        htagadd.add_argument('tagvalue', help="Value of the tag")
        htagadd.add_argument('-m', '--allow-multiple', help="Allow updating tags on multiple identifed instances (otherwise add/edit/delete operations will fail if there is multiple instances)", action='store_true')
        htagadd.add_argument('-p', '--tag-type', choices=['standard', 'extended', 'hostvar'], default='standard', help="Type of tag, standard tags are applied to the instance in AWS, extended tags only exist in the ams database to give you the ability to add tags beyond AWS limitations. Hostvars are variables that are only used by ams-inventory to add host variables into dynamic inventory.")
        htagadd.set_defaults(func=self.command_tag)

        # ams host tag edit
        htagedit = htagsubparser.add_parser('edit', help="Edit tag on an instance or group of instances", parents=[htagargs], formatter_class=SmartFormatter)
        htagedit.add_argument('tagname', help="Name of the tag")
        htagedit.add_argument('tagvalue', help="Value of the tag")
        htagedit.add_argument('-m', '--allow-multiple', help="Allow updating tags on multiple identifed instances (otherwise add/edit/delete operations will fail if there is multiple instances)", action='store_true')
        htagedit.add_argument('-p', '--tag-type', choices=['standard', 'extended'], default='standard', help="Type of tag, standard tags are applied to the instance in AWS, extended tags only exist in the ams database to give you the ability to add tags beyond AWS limitations")
        htagedit.set_defaults(func=self.command_tag)

        # ams host tag delete
        htagdelete = htagsubparser.add_parser('delete', help="Delete a tag from an instance or group of instances", parents=[htagargs], formatter_class=SmartFormatter)
        htagdelete.add_argument('tagname', help="Name of the tag")
        htagdelete.add_argument('-m', '--allow-multiple', help="Allow updating tags on multiple identifed instances (otherwise add/edit/delete operations will fail if there is multiple instances)", action='store_true')
        htagdelete.set_defaults(func=self.command_tag)



    def command_tag(self, args):
        whereclause = ''
        whereval = None
        instance_id = None
        queryvars = []
        if args.instance:
            whereclause = 'hosts.instance_id=%s '
            whereval = args.instance
            instance_id = args.instance
            pass
        elif args.host:
            whereclause = 'hosts.host=%s '
            whereval = args.host
            pass
        elif args.name:
            whereclause = 'hosts.name=%s '
            whereval = args.name
            pass

        if whereval and not instance_id:
            if args.prefix:
                whereclause = whereclause.replace('=', ' like ')
                whereval += '%'
            if args.like:
                whereclause = whereclause.replace('=', ' like ')
                whereval = '%' + whereval + '%'

        if whereclause:
            queryvars.append(whereval)

        filterclauses = []
        filtervals = []
        filterclause = ''
        if args.tag:
            for tagarg in args.tag:
                tagname = None
                tagvalue = None
                operator = '='
                prewild = ''
                postwild = ''
                sumoperator = '>'
                if '!=:' in tagarg:
                    tagname, tagvalue = tagarg.split('!=:', 1)
                    operator = 'like'
                    postwild = '%'
                    sumoperator = '='
                elif '!=~' in tagarg:
                    tagname, tagvalue = tagarg.split('!=~', 1)
                    operator = 'like'
                    postwild = '%'
                    prewild = '%'
                    sumoperator = '='
                elif '!=' in tagarg:
                    tagname, tagvalue = tagarg.split('!=', 1)
                    operator = '='
                    sumoperator = '='
                elif '=~' in tagarg:
                    tagname, tagvalue = tagarg.split('=~', 1)
                    operator = 'like'
                    postwild = '%'
                    prewild = '%'
                elif '=:' in tagarg:
                    tagname, tagvalue = tagarg.split('=:', 1)
                    operator = 'like'
                    postwild = '%'
                elif '=' in tagarg:
                    tagname, tagvalue = tagarg.split('=', 1)
                else:
                    self.logger.error('Unable to parse tag filter, unknown format: "{0}"'.format(tagarg))
                    return

                if tagname and tagvalue:
                    filterclauses.append("sum(tags.name = %s and tags.value {0} %s) {1} 0".format(operator, sumoperator))
                    filtervals.append(tagname)
                    filtervals.append(prewild + tagvalue + postwild)

            if len(filtervals):
                queryvars += filtervals
                filterclause = "having " + " and ".join(filterclauses)


        if whereclause:
            whereclause = "where {0}".format(whereclause)

# select h.instance_id, h.name, h.host, t.name, t.value, t.type from (select hosts.instance_id, hosts.name, hosts.host, tags.name as tagname, tags.value, tags.type from hosts left join tags on tags.resource_id=hosts.instance_id where hosts.name like 'prod.web%' group by instance_id  having sum(tags.name = 'Name' and tags.value = 'prod.web.lb') = 0) as h left join tags t on t.resource_id=h.instance_id

        if args.operation == 'list':
            sql = "select h.instance_id, h.name, h.host, t.name, t.value, t.type from (select hosts.instance_id, hosts.name, hosts.host, tags.name as tagname, tags.value, tags.type from hosts left join tags on tags.resource_id=hosts.instance_id {0} group by instance_id {1}) as h left join tags t on t.resource_id=h.instance_id".format(whereclause, filterclause)
            self.db.execute(sql, queryvars)
            self.logger.debug("Executing query: {0}".format(self.db._last_executed))

            rows = self.db.fetchall()
            results = []
            last_instance_id = ''
            instance_count = 0
            tag_count = 0
            for row in rows:
                tag_count += 1
                result = list(row)
                if self.settings.HUMAN_OUTPUT and result[0] == last_instance_id:
                    result[0] = result[1] = result[2] = ' '
                else:
                    if last_instance_id:
                        results.append([' ', ' ', ' ', ' ', ' ', ' '])
                    last_instance_id = result[0]
                    instance_count += 1
                results.append(result)
            self.output_formatted('Host Tags', ['instance_id', 'name', 'host', 'tag name', 'tag value', 'type'], results, "{0} hosts matched, {1} total tags".format(instance_count, tag_count))
            return

        if not whereclause and not filterclause:
            self.logger.error("One of the arguments -i/--instance -H/--host -e/--name -t/--tag is required to identify instances for tag add/edit/delete operations (accidental global tag editing protection)")
            return
        instance_ids = []
        if not instance_id:
            sql = "select instance_id from hosts left join tags on tags.resource_id=hosts.instance_id {0} group by instance_id {1}".format(whereclause, filterclause)
            self.db.execute(sql, queryvars)
            rows = self.db.fetchall()
            if not rows:
                self.logger.error("No instances found matching {0}".format(whereclause).replace('%s', queryvars).replace('%', '*').replace('hosts.', ''))
            for row in rows:
                if row[0] not in instance_ids:
                    instance_ids.append(row[0])
        else:
            instance_ids = [instance_id]

        if len(instance_ids) > 1 and not args.allow_multiple:
            self.logger.error("{0} instances matched, use --allow-multiple to apply add/edit/delete operation to multiple instances".format(len(instance_ids)))
            return


        if args.operation == 'add' or args.operation == 'edit':
            if not args.tagname or not args.tagvalue:
                self.logger.error("tagname and tagvalue are required for tag add/edit operations")
                return
            for instance_id in instance_ids:
                self.add_tag(instance_id, args.tagname, args.tagvalue, args.tag_type)
            return

        if args.operation == 'delete':
            if not args.tagname:
                self.logger.error("tagname is required for tag delete operation")
                return
            for instance_id in instance_ids:
                self.remove_tag(instance_id, args.tagname)
            return


    def command_discover(self, args):
        self.discover(args.get_unames)

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

        if args.all:
            pass
        elif args.terminated:
            whereclauses.append("`terminated` = 1")
        else:
            whereclauses.append("`terminated` = 0")

        extended = ""
        joins = ""
        groupby = ""
        headers = ["Hostname", "instance_id", "availability_zone", "name", "private ip", "public ip", "notes"]
        if args.extended:
            extended = ", case `terminated` when 0 then 'no' when 1 then 'yes' end"
            headers = ["Hostname", "instance_id", "availability_zone", "name", "private ip", "public ip", "notes", "term"]
        if args.show_tags:
            headers.append('tags')
            extended += ", group_concat(concat(tags.name, ':\t', tags.value) SEPARATOR '\n')"
            joins = " left join tags on tags.resource_id=hosts.instance_id"
            groupby = " group by instance_id"
        sql = "select host, instance_id, availability_zone, hosts.name, ip_internal, ip_external, notes{0} from hosts{1}".format(extended, joins)
        if len(whereclauses):
            sql += " where " + " and ".join(whereclauses)
        sql += groupby
        sql += order_by
        self.db.execute(sql)
        results = self.db.fetchall()

        self.output_formatted("Hosts", headers, results)


    def command_host_add(self, args):
        self.db.execute("insert into hosts(`instance_id`, `host`, `availability_zone`, `hostname_internal`, `hostname_external`, `ip_internal`, "
                   "`ip_external`, `ami_id`, `instance_type`, `notes`, `name`, `uname`) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (args.instance,
                                                                                                         args.hostname,
                                                                                                         args.zone,
                                                                                                         args.hostname_internal,
                                                                                                         args.hostname_external,
                                                                                                         args.ip_internal,
                                                                                                         args.ip_external,
                                                                                                         args.ami_id,
                                                                                                         args.instance_type,
                                                                                                         args.notes,
                                                                                                         args.name,
                                                                                                         args.uname))
        self.dbconn.commit()
        self.logger.info("Added instance {0}({1}) to list of managed hosts".format(args.hostname, args.instance))

    def command_host_edit(self, args):
        fields = ['hostname_internal', 'hostname_external', 'ip_internal', 'ip_external', 'ami_id', 'instance_type', 'notes', 'name', 'uname']
        updates = []
        vars = []
        if args.hostname:
            updates.append("host=%s")
            vars.append(args.hostname)
        if args.hostname == "":
            updates.append("host=NULL")
        if args.zone:
            updates.append("availability_zone=%s")
            vars.append(args.zone)

        for f in fields:
            val = getattr(args, f)
            if val:
                updates.append("{0}=%s".format(f))
                vars.append(val)
            if val == "":
                updates.append("{0}=NULL".format(f))
        write_db = True
        if len(updates) == 0:
            self.logger.info("Nothing to update")
            write_db = False

        if write_db:
            vars.append(args.instance)
            self.db.execute("update hosts set " + ", ".join(updates) + " where instance_id=%s", vars)
            self.dbconn.commit()
            self.logger.info("Instance %s updated", args.instance)

        if args.configure_hostname:
            self.db.execute("select host from hosts where instance_id=%s", (args.instance, ))
            row = self.db.fetchone()
            hostname = row[0]
            self.configure_hostname(args.instance, hostname, True)
