import boto.ec2
import argparse
from amslib.core.manager import BaseManager
from amslib.ssh.sshmanager import SSHManager
import time

class InstanceManager(BaseManager):

    def __get_boto_conn(self, region):
        if region not in self.boto_conns:
            self.boto_conns[region] = boto.ec2.connect_to_region(region, aws_access_key_id=self.settings.AWS_ACCESS_KEY, aws_secret_access_key=self.settings.AWS_SECRET_KEY)
        return self.boto_conns[region]

    def discover(self, get_unames = False):
        regions = boto.ec2.regions()
        instance_ids = []
        for region in regions:
            self.logger.info("Processing region".format(region.name))
            botoconn = self.__get_boto_conn(region.name)
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
                                "ip_internal=%s, ip_external=%s, ami_id=%s, instance_type=%s, availability_zone=%s, name=%s, uname=%s on duplicate "
                                "key update hostname_internal=%s, hostname_external=%s, ip_internal=%s, ip_external=%s, ami_id=%s, "
                                "instance_type=%s, availability_zone=%s, name=%s, host=COALESCE(host, %s)", (i.id, hn, hint, hext,
                                                                            i.private_ip_address, i.ip_address, i.image_id, i.instance_type,
                                                                            i.placement, name, uname, hint, hext, i.private_ip_address,
                                                                            i.ip_address, i.image_id, i.instance_type, i.placement, name, hn))
                self.dbconn.commit()

        self.db.execute("update hosts set `terminated`=0 where instance_id in ('{0}')".format("','".join(instance_ids)))
        self.dbconn.commit()
        self.db.execute("update hosts set `terminated`=1 where instance_id not in ('{0}')".format("','".join(instance_ids)))
        self.dbconn.commit()


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

        sh = SSHManager()
        sh.connect(hostname=hostname, port=self.settings.SSH_PORT, username=self.settings.SSH_USER, password=self.settings.SSH_PASSWORD, key_filename=self.settings.SSH_KEYFILE)

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


    def argument_parser_builder(self, parser):

        hsubparser = parser.add_subparsers(title="action", dest='action')

        # ams host list
        hlistparser = hsubparser.add_parser("list", help="list currently managed hosts")
        hlistparser.add_argument('search_field', nargs="?", help="field to search (host or instance_id)", choices=['host', 'instance_id'])
        hlistparser.add_argument('field_value', nargs="?", help="exact match search value")
        hlistparser.add_argument("--like", help="string to find within 'search-field'")
        hlistparser.add_argument("--prefix", help="string to prefix match against 'search-field'")
        hlistparser.add_argument("--zone", help="Availability zone to filter results by. This is a prefix search so any of the following is valid with increasing specificity: 'us', 'us-west', 'us-west-2', 'us-west-2a'")
        hlistparser.add_argument("-x", "--extended", help="Show extended information on hosts", action='store_true')
        hlistparser.add_argument("-a", "--all", help="Include terminated instances (that have been added via discovery)", action='store_true')
        hlistparser.add_argument("-t", "--terminated", help="Show only terminated instances (that have been added via discovery)", action='store_true')
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
        headers = ["Hostname", "instance_id", "availability_zone", "name", "notes"]
        if args.extended:
            extended = ", case `terminated` when 0 then 'no' when 1 then 'yes' end, ip_internal, ip_external, hostname_internal, hostname_external"
            headers = ["Hostname", "instance_id", "availability_zone", "name", "notes", "term", "int ip", "ext ip", "int hostname", "ext hostname"]
        sql = "select host, instance_id, availability_zone, name, notes{0} from hosts".format(extended)
        if len(whereclauses):
            sql += " where " + " and ".join(whereclauses)
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
            self.logger.info("Instance {0} updated", args.instance);

        if args.configure_hostname:
            self.db.execute("select host from hosts where instance_id=%s", (args.instance, ))
            row = self.db.fetchone()
            hostname = row[0]
            self.configure_hostname(args.instance, hostname, True)
