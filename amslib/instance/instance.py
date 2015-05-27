import boto.ec2
import argparse
from amslib.core.manager import BaseManager
from amslib.core.formatter import ArgParseSmartFormatter
from amslib.ssh.sshmanager import SSHManager
from amslib.core.completion import ArgumentCompletion
from amslib.core.completion import HostTemplateArgumentCompletion
from errors import *
import time
from pprint import pprint
import json


class InstanceManager(BaseManager):

    def __get_boto_conn(self, region):
        if region not in self.boto_conns:
            self.boto_conns[region] = boto.ec2.connect_to_region(region, aws_access_key_id=self.settings.AWS_ACCESS_KEY, aws_secret_access_key=self.settings.AWS_SECRET_KEY)
        return self.boto_conns[region]

    def __subinit__(self):
        self.instance_types = [
            # Instance Types listed here: http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-types.html
            # current gen
            't2.micro','t2.small','t2.medium','m3.medium','m3.large','m3.xlarge','m3.2xlarge',
            'c4.large','c4.xlarge','c4.2xlarge','c4.4xlarge','c4.8xlarge','c3.large','c3.xlarge','c3.2xlarge','c3.4xlarge','c3.8xlarge',
            'r3.large','r3.xlarge','r3.2xlarge','r3.4xlarge','r3.8xlarge',
            'i2.xlarge','i2.2xlarge','i2.4xlarge','i2.8xlarge', 'd2.xlarge', 'd2.2xlarge', 'd2.4xlarge', 'd2.8xlarge',
            'g2.2xlarge',
            # previous gen
            't1.micro','m1.small','m1.medium','m1.large','m1.xlarge',
            'c1.medium','c1.xlarge','cc2.8xlarge',
            'm2.xlarge','m2.2xlarge','m2.4xlarge',
            'cr1.8xlarge','hi1.4xlarge','hs1.8xlarge',
            'cg1.4xlarge'
        ]
        # PV vs HVM comapatibility can be found here: http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/virtualization_types.html
        self.paravirtual = [
            't1', 'c1', 'cc2', 'm1', 'm2', 'hi1', 'hs1', 'cg1',
            'm3', 'c3', 'c4', 'd2'
        ]
        self.hvm = [
            'cc2', 'hi1', 'hs1', 'cg1',
            't2', 'm3', 'c3', 'c4', 'r3', 'i2', 'd2', 'g2'
        ]

    def load_amis(self, region):
        botoconn = self.__get_boto_conn(region)
        try:

            images = botoconn.get_all_images(owners=['self'])
            self.db.execute('update amis set active=0 where region=%s', (region, ))
            self.dbconn.commit()
            for i in images:
                #TODO this is getting ridiculous...I think it is time to write a nice insert/update helper that takes a table name and dict of column values to make these much cleaner
                sql = "insert into amis set ami_id=%s, region=%s, name=%s, description=%s, location=%s, state=%s, owner_id=%s, " \
                      "owner_alias=%s, is_public=%s, architecture=%s, platform=%s, type=%s, kernel_id=%s, ramdisk_id=%s, " \
                      "product_codes=%s, billing_products=%s, root_device_type=%s, root_device_name=%s, virtualization_type=%s, " \
                      "hypervisor=%s, sriov_net_support=%s, active=1 on duplicate key update " \
                      "region=%s, name=%s, description=%s, location=%s, state=%s, owner_id=%s, " \
                      "owner_alias=%s, is_public=%s, architecture=%s, platform=%s, type=%s, kernel_id=%s, ramdisk_id=%s, " \
                      "product_codes=%s, billing_products=%s, root_device_type=%s, root_device_name=%s, virtualization_type=%s, " \
                      "hypervisor=%s, sriov_net_support=%s, active=1"

                insertvars = [
                    i.id, region, i.name, i.description, i.location, i.state, i.owner_id, i.owner_alias, i.is_public,
                    i.architecture, i.platform, i.type, i.kernel_id, i.ramdisk_id, json.dumps(i.product_codes), json.dumps(i.billing_products),
                    i.root_device_type, i.root_device_name, i.virtualization_type, i.hypervisor, i.sriov_net_support,
                    region, i.name, i.description, i.location, i.state, i.owner_id, i.owner_alias, i.is_public,
                    i.architecture, i.platform, i.type, i.kernel_id, i.ramdisk_id, json.dumps(i.product_codes), json.dumps(i.billing_products),
                    i.root_device_type, i.root_device_name, i.virtualization_type, i.hypervisor, i.sriov_net_support
                ]
                self.db.execute(sql, insertvars)
                self.dbconn.commit()

                self.db.execute("update ami_block_devices set active=0 where ami_id=%s", (i.id, ))
                self.dbconn.commit()
                for mount_point, block_device_type in i.block_device_mapping.iteritems():
                    sql = "insert into ami_block_devices set ami_id=%s, device_name=%s, ephemeral_name=%s, snapshot_id=%s, " \
                          "delete_on_termination=%s, size=%s, volume_type=%s, iops=%s, encrypted=%s, active=1 on duplicate key update " \
                          "ephemeral_name=%s, snapshot_id=%s, delete_on_termination=%s, size=%s, volume_type=%s, iops=%s, encrypted=%s, active=1"
                    insertvars = [
                        i.id, mount_point, block_device_type.ephemeral_name, block_device_type.snapshot_id, block_device_type.delete_on_termination,
                        block_device_type.size, block_device_type.volume_type, block_device_type.iops, block_device_type.encrypted,
                        block_device_type.ephemeral_name, block_device_type.snapshot_id, block_device_type.delete_on_termination,
                        block_device_type.size, block_device_type.volume_type, block_device_type.iops, block_device_type.encrypted
                    ]
                    self.db.execute(sql, insertvars)
                    self.dbconn.commit()

                self.db.execute("delete from ami_block_devices where active=0")
                self.dbconn.commit()
                self.db.execute("select ami_id from amis where active=0")
                ids = self.db.fetchall()
                if ids:
                    for ami_id in ids:
                        self.db.execute("delete from ami_block_devices where ami_id=%s", (ami_id[0], ))
                        self.dbconn.commit()
                        self.db.execute('delete from amis where ami_id=%s', (ami_id[0], ))
                        self.dbconn.commit()
        except boto.exception.EC2ResponseError as e:
            if e.code != 'AuthFailure':
                raise


    def load_zones(self, region):
        botoconn = self.__get_boto_conn(region)
        self.db.execute("update availability_zones set active=0 where region=%s", (region, ))
        self.dbconn.commit()
        try:
            zones = botoconn.get_all_zones()
            for zone in zones:
                self.db.execute("insert into availability_zones set availability_zone=%s, region=%s, active=1 on duplicate key update active=1", (zone.name, region))
                self.dbconn.commit()
        except:
            pass


    def load_keypairs(self, region):
        botoconn = self.__get_boto_conn(region)
        self.db.execute("update key_pairs set active=0 where region=%s",(region, ))
        self.dbconn.commit()
        try:
            keypairs = botoconn.get_all_key_pairs()
            for kp in keypairs:
                self.db.execute("insert into key_pairs set region=%s, key_name=%s, fingerprint=%s, active=1 on duplicate key update fingerprint=%s, active=1", (region, kp.name, kp.fingerprint, kp.fingerprint))
                self.dbconn.commit()
        except:
            pass
        self.db.execute("delete from key_pairs where region=%s and active=0", (region, ))
        self.dbconn.commit()


    def store_instance(self, instance, get_uname=False):
        name = None
        if 'Name' in instance.tags:
            name = instance.tags['Name']
        hint = None
        hext = None
        hn = None
        if instance.private_dns_name:
            hint = instance.private_dns_name
        if instance.public_dns_name:
            hext = instance.public_dns_name
        if instance.dns_name:
            hn = instance.dns_name

        uname = None
        if get_uname:
            # TODO implement the ssh call to the host to gather the uname
            pass

        self.db.execute("insert into hosts set instance_id=%s, host=%s, hostname_internal=%s, hostname_external=%s, "
                        "ip_internal=%s, ip_external=%s, ami_id=%s, instance_type=%s, availability_zone=%s, name=%s, uname=%s, vpc_id=%s, "
                        "subnet_id=%s, key_name=%s, `terminated`=0 on duplicate key update hostname_internal=%s, hostname_external=%s, ip_internal=%s, ip_external=%s, ami_id=%s, "
                        "instance_type=%s, availability_zone=%s, name=%s, host=COALESCE(host, %s), vpc_id=%s, subnet_id=%s, key_name=%s, `terminated`=0", (instance.id, hn, hint, hext,
                                                                    instance.private_ip_address, instance.ip_address, instance.image_id, instance.instance_type,
                                                                    instance.placement, name, uname, instance.vpc_id, instance.subnet_id, instance.key_name, hint, hext, instance.private_ip_address,
                                                                    instance.ip_address, instance.image_id, instance.instance_type, instance.placement, name, hn, instance.vpc_id, instance.subnet_id, instance.key_name))
        self.dbconn.commit()
        self.store_ec2_tags(instance)



    def discover(self, get_unames = False):
        regions = boto.ec2.regions()
        for region in regions:
            instance_ids = []
            self.logger.info("Processing region {0}".format(region.name))
            botoconn = self.__get_boto_conn(region.name)

            self.load_zones(region.name)
            self.load_amis(region.name)
            self.load_keypairs(region.name)

            self.logger.info("Getting instances")
            try:
                instances = botoconn.get_only_instances()
            except boto.exception.EC2ResponseError:
                continue
            for i in instances:
                instance_ids.append(i.id)
                self.logger.info("Found instance {0}".format(i.id))
                self.store_instance(i, get_unames)

            self.db.execute("update hosts set `terminated`=0 where instance_id in ('{0}')".format("','".join(instance_ids)))
            self.dbconn.commit()
            self.db.execute("update hosts set `terminated`=1 where instance_id not in ('{0}') and availability_zone like %s".format("','".join(instance_ids)), (region.name + '%', ))
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
        if tagname == 'Name':
            self.db.execute("update hosts set name=%s where instance_id=%s", (tagvalue, instance_id))
            self.dbconn.commit()
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


    def create_instance(self, region, ami_id, instance_type, number=1, keypair=None, zone=None, monitoring=None, vpc_id=None, subnet_id=None, private_ip=None, security_groups=[], ebs_optimized=None, tags={}):
        if not keypair:
            if self.settings.DEFAULT_KEYPAIR:
                keypair = self.settings.DEFAULT_KEYPAIR
        reservation = None
        botoconn = self.__get_boto_conn(region)


        # apply proper defaults for things that need them
        if monitoring is None:
            monitoring = False
        if ebs_optimized is None:
            ebs_optimized = False

        if vpc_id or subnet_id:
            if not subnet_id:
                self.logger.error("subnet must be provided for a vpc instance")
                return
            reservation = botoconn.run_instances(image_id=ami_id, instance_type=instance_type, min_count=number, monitoring_enabled=monitoring, max_count=number, key_name=keypair, ebs_optimized=ebs_optimized, security_group_ids=security_groups, subnet_id=subnet_id, private_ip_address=private_ip)
        else:
            reservation = botoconn.run_instances(image_id=ami_id, instance_type=instance_type, min_count=number, monitoring_enabled=monitoring, max_count=number, key_name=keypair, ebs_optimized=ebs_optimized, placement=zone, security_groups=security_groups)

        if reservation:
            # we need to give amazon a moment to get the instance into an existent state
            time.sleep(3)
            for instance in reservation.instances:
                instance.update()
                c = 0
                while instance.state == 'pending':
                    if (c % 10) == 0:
                        self.logger.info("Waiting on instance {0} to become available".format(instance.id))
                    time.sleep(1)
                    instance.update()

                self.logger.info("Created instance: {0}".format(instance.id))
                self.store_instance(instance)
                for sg in security_groups:
                    # TODO this should be relocated to exist in amslib.network.general.NetorkManager in some form, once the different parts of discovery are untangled
                    self.db.execute("insert into security_group_associations set security_group_id=%s, instance_id=%s", (sg, instance.id))
                    self.dbconn.commit()
                for tagname, tagvalue in tags.iteritems():
                    self.add_tag(instance.id, tagname, tagvalue)
                    if tagname == 'Name':
                        self.db.execute("update hosts set name=%s where instance_id=%s", (tagvalue, instance.id))
                        self.dbconn.commit()


    def control_instances(self, action, instance_ids=[]):
        if not len(instance_ids):
            raise InstanceNotFound("No instances provided")
        regions = {}
        self.db.execute("select instance_id, availability_zone from hosts where instance_id in ({0})".format(", ".join(['%s' for x in range(len(instance_ids))])), instance_ids)
        rows = self.db.fetchall()
        if not rows:
            raise InstanceNotFound("No instances found matching given instance_ids")
        for row in rows:
            instance_id, az = row
            region = self.parse_region_from_availability_zone(az)
            if region not in regions:
                regions[region] = []
            regions[region].append(instance_id)

        actioned = {}
        for region in regions:
            actioned[region] = []
            botoconn = self.__get_boto_conn(region)
            if action == 'start':
                self.logger.info("starting instances in region: {0}".format(region))
                fn = botoconn.start_instances
            elif action == 'stop':
                self.logger.info("stopping instances in region: {0}".format(region))
                fn = botoconn.stop_instances
            elif action == 'reboot':
                self.logger.info("rebooting instances in region: {0}".format(region))
                fn = botoconn.reboot_instances
            elif action == 'terminate':
                self.logger.info("terminating instances in region: {0}".format(region))
                fn = botoconn.terminate_instances
            else:
                raise InvalidInstanceAction("{0} is not a valid control action for an instance".format(action))

            done = fn(regions[region])
            # apparently reboot just returns true or false whether it was successful or not (argh at lack of consistency)
            if action == 'reboot':
                if done:
                    actioned[region] = regions[region]
                continue
            for i in done:
                actioned[region].append(i.id)
                if action == 'terminate':
                    self.db.execute("update hosts set `terminated`=1 where instance_id=%s", (i.id, ))
                    self.dbconn.commit()

        return actioned

    def argparse_stub(self):
        return 'host'


    def argparse_help_text(self):
        return 'direct host/instance related operations'


    def argument_parser_builder(self, parser):
        ac = ArgumentCompletion(self.settings)
        htac = HostTemplateArgumentCompletion(self.settings)

        hsubparser = parser.add_subparsers(title="action", dest='action')

        # ams host list
        hlistparser = hsubparser.add_parser("list", help="list currently managed hosts", formatter_class=ArgParseSmartFormatter)
        hlistparser.add_argument('search_field', nargs="?", help="field to search (host or instance_id)", choices=['host', 'instance_id', 'name'])
        hlistparser.add_argument('field_value', nargs="?", help="exact match search value")
        hlistparser.add_argument("--like", help="string to find within 'search-field'")
        hlistparser.add_argument("--prefix", help="string to prefix match against 'search-field'")
        hlistparser.add_argument("--zone", help="Availability zone to filter results by. This is a prefix search so any of the following is valid with increasing specificity: 'us', 'us-west', 'us-west-2', 'us-west-2a'").completer = ac.availability_zone
        hlistparser.add_argument("-x", "--extended", help="Show extended information on hosts", action='store_true')
        hlistparser.add_argument("-a", "--all", help="Include terminated instances (that have been added via discovery)", action='store_true')
        hlistparser.add_argument("--terminated", help="Show only terminated instances (that have been added via discovery)", action='store_true')
        hlistparser.add_argument("-s", "--show-tags", help="Display tags for instances", action='store_true')
        hlistparser.add_argument('-t', '--tag', help="R|Filter instances by tag, in the form name<OPERATOR>value.\nValid operators: \n\t=\t(equal)\n\t!=\t(not equal)\n\t=~\t(contains/like)\n\t!=~\t(not contains/not like)\n\t=:\t(prefixed by)\n\t!=:\t(not prefixed by)\nEg. To match Name tag containing 'foo': --tag Name=~foo", action='append')
        hlistparser.set_defaults(func=self.command_host_list)

        # hsubparser.add_parser("info", help="Get information on a host")

        addeditargs = argparse.ArgumentParser(add_help=False)
        addeditargs.add_argument('-i', '--instance', help="Instance ID of the instance to add", required=True).completer = ac.instance_id
        addeditargs.add_argument('-u', '--uname', help="Hostname to use when setting uname on the host (default is to use instance hostname)")
        addeditargs.add_argument('--hostname-internal', help="Internal hostname")
        addeditargs.add_argument('--hostname-external', help="External hostname")
        addeditargs.add_argument('--ip-internal', help="Internal IP address")
        addeditargs.add_argument('--ip-external', help="External IP address")
        addeditargs.add_argument('--ami-id', help="AMI ID")
        addeditargs.add_argument('--instance-type', help="Instance type (stored but not currently used)", metavar='INSTANCE_TYPE', choices=self.instance_types)
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
        heditparser.add_argument('-z', '--zone', help="Availability zone that the instance is in").completer = ac.availability_zone
        heditparser.set_defaults(func=self.command_host_edit)

        # ams host create
        hcreateparser = hsubparser.add_parser("create", help="Create a new instance")
        hcreateparser.add_argument('-r', '--region', help="Region to create the instance in").completer = htac.region
        hcreateparser.add_argument('-y', '--instance-type', help="EC2 instance type", metavar='INSTANCE_TYPE', choices=self.instance_types)
        hcreateparser.add_argument('-m', '--ami-id', help="AMI ID for the new instance").completer = htac.ami_id
        hcreateparser.add_argument('-k', '--key-name', help="Keypair name to use for creating instance").completer = htac.keypair
        hcreateparser.add_argument('-z', '--zone', help="Availability zone to create the instance in").completer = htac.availability_zone
        hcreateparser.add_argument('-o', '--monitoring', action='store_true', help="Enable detailed cloudwatch monitoring", default=None)
        hcreateparser.add_argument('-v', '--vpc-id', help="VPC ID (Not required, used to aid autocomplete for subnet id)").completer = htac.vpc_id
        hcreateparser.add_argument('-s', '--subnet-id', help="Subnet ID for VPC").completer = htac.subnet_id
        hcreateparser.add_argument('-i', '--private-ip', help="Private IP address to assign to instance (VPC only)")
        hcreateparser.add_argument('-g', '--security-group', action='append', help="Security group to associate with instance (supports multiple usage)", default=[]).completer = htac.security_group_id
        hcreateparser.add_argument('-e', '--ebs-optimized', action='store_true', help="Enable EBS optimization", default=None)
        hcreateparser.add_argument('-n', '--number', type=int, default=1, help="Number of instances to create")
        hcreateparser.add_argument('-a', '--name', help="Set the name tag for created instance")
        hcreateparser.add_argument('-t', '--tag', action='append', help="Add tag to the instance in the form tagname=tagvalue, eg: --tag my_tag=my_value (supports multiple usage)")
        group = hcreateparser.add_mutually_exclusive_group()
        group.add_argument('--template-id', help="Set a host template id to use to create instance").completer = ac.host_template_id
        group.add_argument('--template-name', help="Set a host template name to use to create instance").completer = ac.host_template_name
        hcreateparser.set_defaults(func=self.command_host_create)


        # ams host discovery
        discparser = hsubparser.add_parser("discovery", help="Run discovery on hosts/instances to populate database with resources")
        discparser.add_argument("--get-unames", action='store_true', help="Connects to each server to query the system's uname, much slower discovery due to ssh to each host (not implemented yet)")
        discparser.set_defaults(func=self.command_discover)


        # ams host template
        htempparser = hsubparser.add_parser('template', help="Management of host creation templates")
        htempsubparser = htempparser.add_subparsers(title='operation', dest='operation')

        # ams host template list
        htemplistparser = htempsubparser.add_parser('list', help="List available host creation templates")
        group = htemplistparser.add_mutually_exclusive_group()
        group.add_argument('--template-id', help="Filter by template ID").completer = ac.host_template_id
        group.add_argument('--template-name', help="Filter by template name").completer = ac.host_template_name
        htemplistparser.add_argument('-r', '--region', help="Filter by region").completer = ac.region
        htemplistparser.add_argument('-m', '--ami-id', help="Filter by AMI ID").completer = ac.ami_id
        htemplistparser.add_argument('-z', '--zone', help="Filter by availability zone").completer = ac.availability_zone
        htemplistparser.add_argument('-v', '--vpc-id', help="Filter by VPC ID").completer = ac.vpc_id
        htemplistparser.add_argument('-s', '--subnet-id', help="Filter by VPC Subnet ID").completer = ac.subnet_id
        htemplistparser.add_argument('-i', '--private-ip', help="Filter by private IP")
        htemplistparser.add_argument('-a', '--name', help="Set the name tag for created instance")
        htemplistparser.add_argument('--sort', nargs='+', help="Sort by given one or more of the fields: template-id, template-name, region, instance-type, ami-id, zone, vpc-id, subnet-id, name", choices=['template-id', 'template-name', 'region', 'instance-type', 'ami-id', 'zone', 'vpc-id', 'subnet-id', 'name'], metavar='FIELD', default=[])
        htemplistparser.set_defaults(func=self.command_host_template_list)

        # ams host template create
        htempcreateparser = htempsubparser.add_parser('create', help="Create a new host template")
        htempcreateparser.add_argument('-n', '--template-name', required=True, help="Unique name for the template")
        htempcreateparser.add_argument('-r', '--region', help="Region to create the instance in").completer = ac.region
        htempcreateparser.add_argument('-y', '--instance-type', help="EC2 instance type", metavar='INSTANCE_TYPE', choices=self.instance_types)
        htempcreateparser.add_argument('-m', '--ami-id', help="AMI ID for the new instance").completer = ac.ami_id
        htempcreateparser.add_argument('-k', '--key-name', help="Keypair name to use for creating instance").completer = ac.keypair
        htempcreateparser.add_argument('-z', '--zone', help="Availability zone to create the instance in").completer = ac.availability_zone
        htempcreateparser.add_argument('-o', '--monitoring', action='store_true', help="Enable detailed cloudwatch monitoring", default=None)
        htempcreateparser.add_argument('-v', '--vpc-id', help="VPC ID (Not required, used to aid autocomplete for subnet id)").completer = ac.vpc_id
        htempcreateparser.add_argument('-s', '--subnet-id', help="Subnet ID for VPC").completer = ac.subnet_id
        htempcreateparser.add_argument('-i', '--private-ip', help="Private IP address to assign to instance (VPC only)")
        htempcreateparser.add_argument('-g', '--security-group', action='append', help="Security group to associate with instance (supports multiple usage)", default=[]).completer = ac.security_group_id
        htempcreateparser.add_argument('-e', '--ebs-optimized', action='store_true', help="Enable EBS optimization", default=None)
        htempcreateparser.add_argument('-a', '--name', help="Set the name tag for created instance")
        htempcreateparser.add_argument('-t', '--tag', action='append', help="Add tag to the instance in the form tagname=tagvalue, eg: --tag my_tag=my_value (supports multiple usage)", default=[])
        htempcreateparser.set_defaults(func=self.command_host_template_create)

        # ams host template edit
        htempeditparser = htempsubparser.add_parser('edit', help="Modify an existing host template")
        group = htempeditparser.add_mutually_exclusive_group(required=True)
        group.add_argument('--template-id', help="Set a host template id to edit").completer = ac.host_template_id
        group.add_argument('--template-name', help="Set a host template name to edit").completer = ac.host_template_name
        htempeditparser.add_argument('-r', '--region', help="Region to create the instance in").completer = htac.region
        htempeditparser.add_argument('-y', '--instance-type', help="EC2 instance type", metavar='INSTANCE_TYPE', choices=self.instance_types)
        htempeditparser.add_argument('-m', '--ami-id', help="AMI ID for the new instance").completer = htac.ami_id
        htempeditparser.add_argument('-k', '--key-name', help="Keypair name to use for creating instance").completer = htac.keypair
        htempeditparser.add_argument('-z', '--zone', help="Availability zone to create the instance in").completer = htac.availability_zone
        htempeditparser.add_argument('-o', '--monitoring', action='store_true', help="Enable detailed cloudwatch monitoring", default=None)
        htempeditparser.add_argument('-v', '--vpc-id', help="VPC ID (Not required, used to aid autocomplete for subnet id)").completer = htac.vpc_id
        htempeditparser.add_argument('-s', '--subnet-id', help="Subnet ID for VPC").completer = htac.subnet_id
        htempeditparser.add_argument('-i', '--private-ip', help="Private IP address to assign to instance (VPC only)")
        htempeditparser.add_argument('-g', '--security-group', action='append', help="Security group to associate with instance (supports multiple usage)", default=[]).completer = htac.security_group_id
        htempeditparser.add_argument('-e', '--ebs-optimized', action='store_true', help="Enable EBS optimization", default=None)
        htempeditparser.add_argument('-a', '--name', help="Set the name tag for created instance")
        htempeditparser.add_argument('-t', '--tag', action='append', help="Add tag to the instance in the form tagname=tagvalue, eg: --tag my_tag=my_value (supports multiple usage)", default=[])
        htempeditparser.add_argument('--new-template-name', help="Change the template-name for the given template")
        htempeditparser.add_argument('--remove', action='append', help="Remove the value for one of the settings: instance-type, ami-id, key-name, zone, monitoring, vpc-id, subnet-id, private-ip, ebs-optimized, name (supports multiple usage)", choices=['instance-type', 'ami-id', 'key-name', 'zone', 'monitoring', 'vpc-id', 'subnet-id', 'private-ip', 'ebs-optimized', 'name'], default=[])
        htempeditparser.add_argument('--remove-tag', action='append', help="Remove a tag by name from the template (supports multiple usage)", default=[])
        htempeditparser.add_argument('--remove-security-group', action='append', help="Remove a security group by id from the template (supports multiple usage)", default=[])
        htempeditparser.set_defaults(func=self.command_host_template_edit)

        # ams host template delete
        htempdelparser = htempsubparser.add_parser('delete', help="Delete a host template (has no effect on hosts that have been created using the template)")
        group = htempdelparser.add_mutually_exclusive_group(required=True)
        group.add_argument('--template-id', help="Set a host template id to delete")
        group.add_argument('--template-name', help="Set a host template name to delete")
        htempdelparser.set_defaults(func=self.command_host_template_delete)

        # ams host template copy
        htempcopyparser = htempsubparser.add_parser('copy', help="Copy an existing template to a new template")
        group = htempcopyparser.add_mutually_exclusive_group(required=True)
        group.add_argument('--template-id', help="Source template ID")
        group.add_argument('--template-name', help="Source template name")
        htempcopyparser.add_argument('--name', required=True, help="Name for the new template")
        htempcopyparser.set_defaults(func=self.command_host_template_copy)


        # ams host control
        hcontrolparser = hsubparser.add_parser("control", help="Control the running state of hosts")
        hcontrolparser.add_argument('instance_action', help="Action to take on host", choices=['start', 'stop', 'reboot', 'terminate'])
        hcontrolparser.add_argument('instances', nargs='+', help="Instance ID to take action on ").completer = ac.instance_id
        hcontrolparser.add_argument('--execute', action='store_true', help="Applies the action to the given instances, otherwise, a list of instances that would be shut down is listed")
        hcontrolparser.set_defaults(func=self.command_control)


        # ams host tag
        htagargs = argparse.ArgumentParser(add_help=False)
        htagargs.add_argument('--prefix', help="For host/name identification, treats the given string as a prefix", action='store_true')
        htagargs.add_argument('--like', help="For host/name identification, searches for instances that contain the given string", action='store_true')
        htagargs.add_argument('-t', '--tag', help="R|Filter instances by tag, in the form name<OPERATOR>value.\nValid operators: \n\t=\t(equal)\n\t!=\t(not equal)\n\t=~\t(contains/like)\n\t!=~\t(not contains/not like)\n\t=:\t(prefixed by)\n\t!=:\t(not prefixed by)\nEg. To match Name tag containing 'foo': --tag Name=~foo", action='append')
        htaggroup = htagargs.add_mutually_exclusive_group()
        htaggroup.add_argument('-i', '--instance', help="instance_id of an instance to manage tags").completer = ac.instance_id
        htaggroup.add_argument('-H', '--host', help="hostname of an instance to manage tags")
        htaggroup.add_argument('-e', '--name', help="name of an instance to manage tags")

        htagparser = hsubparser.add_parser("tag", help="Manage tags for instances")
        htagsubparser = htagparser.add_subparsers(title="operation", dest='operation')

        # ams host tag list
        htaglist = htagsubparser.add_parser('list', help="List instance tags", parents=[htagargs], formatter_class=ArgParseSmartFormatter)
        htaglist.set_defaults(func=self.command_tag)

        # ams host tag add
        htagadd = htagsubparser.add_parser('add', help="Add tag to an instance or group of instances", parents=[htagargs], formatter_class=ArgParseSmartFormatter)
        htagadd.add_argument('tagname', help="Name of the tag")
        htagadd.add_argument('tagvalue', help="Value of the tag")
        htagadd.add_argument('-m', '--allow-multiple', help="Allow updating tags on multiple identifed instances (otherwise add/edit/delete operations will fail if there is multiple instances)", action='store_true')
        htagadd.add_argument('-p', '--tag-type', choices=['standard', 'extended', 'hostvar'], default='standard', help="Type of tag, standard tags are applied to the instance in AWS, extended tags only exist in the ams database to give you the ability to add tags beyond AWS limitations. Hostvars are variables that are only used by ams-inventory to add host variables into dynamic inventory.")
        htagadd.set_defaults(func=self.command_tag)

        # ams host tag edit
        htagedit = htagsubparser.add_parser('edit', help="Edit tag on an instance or group of instances", parents=[htagargs], formatter_class=ArgParseSmartFormatter)
        htagedit.add_argument('tagname', help="Name of the tag")
        htagedit.add_argument('tagvalue', help="Value of the tag")
        htagedit.add_argument('-m', '--allow-multiple', help="Allow updating tags on multiple identifed instances (otherwise add/edit/delete operations will fail if there is multiple instances)", action='store_true')
        htagedit.add_argument('-p', '--tag-type', choices=['standard', 'extended'], default='standard', help="Type of tag, standard tags are applied to the instance in AWS, extended tags only exist in the ams database to give you the ability to add tags beyond AWS limitations")
        htagedit.set_defaults(func=self.command_tag)

        # ams host tag delete
        htagdelete = htagsubparser.add_parser('delete', help="Delete a tag from an instance or group of instances", parents=[htagargs], formatter_class=ArgParseSmartFormatter)
        htagdelete.add_argument('tagname', help="Name of the tag")
        htagdelete.add_argument('-m', '--allow-multiple', help="Allow updating tags on multiple identifed instances (otherwise add/edit/delete operations will fail if there is multiple instances)", action='store_true')
        htagdelete.set_defaults(func=self.command_tag)

        # ams host keys list
        hkeyparser = hsubparser.add_parser('keys', help="Management of Key Pairs")
        hkeyparser.add_argument('command', help="Command to run", choices=['list'])
        hkeyparser.add_argument('-r', '--region', help="AWS region name").completer = ac.region
        hkeyparser.set_defaults(func=self.command_key)

        # ams host ami
        hamiparser = hsubparser.add_parser("ami", help="Management of AMIs")
        hamisubparser = hamiparser.add_subparsers(title="command", dest='command')
        hamilistparser = hamisubparser.add_parser("list", help="List available AMIs")
        hamilistparser.add_argument('-r', '--region', help="Filter by region").completer = ac.region
        hamilistparser.set_defaults(func=self.command_amilist)


    def command_control(self, args):
        if not args.execute:
            self.db.execute("select instance_id, host, name, availability_zone, vpc_id, subnet_id from hosts where instance_id in ({0})".format(", ".join(['%s' for x in range(len(args.instances))])), args.instances)
            rows = self.db.fetchall()
            if not rows:
                rows = []
            self.output_formatted("Instances to {0}".format(args.instance_action.upper()), ['Instance ID', 'Host', 'Name', 'Availability Zone', 'VPC ID', 'Subnet ID'], rows)
            return

        actioned = self.control_instances(args.instance_action, args.instances)
        output = []
        for region in actioned:
            for instance_id in actioned[region]:
                output.append((instance_id, region))
        self.output_formatted("Successfully applied {0}".format(args.instance_action.upper()), ['Instance ID', 'Region'], output)

    def command_host_template_copy(self, args):
        template_id = args.template_id
        if args.template_name:
            self.db.execute("select template_id from host_templates where template_name=%s", (args.template_name, ))
            row = self.db.fetchone()
            if row:
                template_id = row[0]
            else:
                self.logger.error("Template {0} not found".format(args.template_name))

        if not template_id:
            return

        self.db.execute("select * from host_templates where template_id=%s", (template_id, ))
        row = self.db.fetchone()
        if not row:
            self.logger.error("unable to retrieve template {0}".format(template_id))
            return

        new_row = list(row)
        new_row[0] = None
        new_row[1] = args.name

        self.db.execute("insert into host_templates values({0})".format(", ".join(['%s' for x in range(len(new_row))])), new_row)
        self.dbconn.commit()
        new_template_id = self.db.lastrowid
        self.db.execute("select * from host_template_tags where template_id=%s", (template_id, ))
        rows = self.db.fetchall()
        if rows:
            for row in rows:
                new_row = list(row)
                new_row[0] = new_template_id
                self.db.execute("insert into host_template_tags values ({0})".format(", ".join(['%s' for x in range(len(new_row))])), new_row)
                self.dbconn.commit()

        self.db.execute("select * from host_template_sg_associations where template_id=%s", (template_id, ))
        rows = self.db.fetchall()
        if rows:
            for row in rows:
                new_row = list(row)
                new_row[0] = new_template_id
                self.db.execute("insert into host_template_sg_associations values ({0})".format(", ".join(['%s' for x in range(len(new_row))])), new_row)
                self.dbconn.commit()

        self.logger.info("New template created with id {0}".format(new_template_id))



    def command_host_template_list(self, args):
        fields = ['template_id', 'template_name', 'region', 'ami_id', 'zone', 'vpc_id', 'subnet_id', 'private_ip', 'name']
        wheres = []
        wherevals = []
        for field in fields:
            val = getattr(args, field)
            if val is not None:
                wheres.append("{0}=%s".format(field))
                wherevals.append(val)
        headers = ['template id', 'template name', 'region', 'instance type', 'ami_id', 'keypair', 'zone', 'monitoring', 'vpc_id', 'subnet_id', 'private_ip', 'ebs optimized', 'name', 'security groups', 'tags']
        where = ''
        if len(wheres):
            where = 'where {0}'.format(" and ".join(wheres))
        sorts = ""
        if len(args.sort):
            sorts = "order by `" + "`, `".join([str(x).replace('-', '_') for x in args.sort]) + '`'
        sql = "select h.template_id, template_name, region, instance_type, ami_id, key_name, zone, monitoring, vpc_id, subnet_id, private_ip, if(ebs_optimized, 'yes', 'no'), h.name, group_concat(distinct security_group_id separator '\n'), group_concat(distinct concat(t.name,'=',t.value) separator '\n') from host_templates h left join host_template_tags t using(template_id) left join host_template_sg_associations s using(template_id) {0} group by template_id {1}".format(where, sorts)
        self.db.execute(sql, wherevals)
        rows = self.db.fetchall()
        if not rows:
            rows = []

        self.output_formatted("Host Creation Templates", headers, rows, insert_breaks=1)

    def command_host_template_create(self, args):
        tags = self.__command_parse_tags(args.tag)
        if tags is None:
            return
        self.db.execute("insert into host_templates set template_name=%s, region=%s, instance_type=%s, ami_id=%s, zone=%s, monitoring=%s, vpc_id=%s, subnet_id=%s, private_ip=%s, ebs_optimized=%s, `name`=%s",
            (args.template_name, args.region, args.instance_type, args.ami_id, args.zone, args.monitoring, args.vpc_id, args.subnet_id, args.private_ip, args.ebs_optimized, args.name))
        self.dbconn.commit()
        template_id = self.db.lastrowid
        for sg in args.security_group:
            self.db.execute("insert into host_template_sg_associations set template_id=%s, security_group_id=%s on duplicate key update security_group_id=%s",(template_id, sg, sg))
            self.dbconn.commit()
        for tagname, tagvalue in tags.iteritems():
            self.db.execute("insert into host_template_tags set template_id=%s, `name`=%s, `value`=%s on duplicate key update `value`=%s",(template_id, tagname, tagvalue, tagvalue))
            self.dbconn.commit()


    def command_host_template_edit(self, args):
        tags = self.__command_parse_tags(args.tag)
        if tags is None:
            return
        template_id = args.template_id
        if args.template_name:
            self.db.execute("select template_id from host_templates where template_name=%s", (args.template_name, ))
            row = self.db.fetchone()
            if row:
                template_id = row[0]
            else:
                self.logger.error("Template {0} not found".format(args.template_name))

        if template_id:
            fields = ['instance_type', 'ami_id', 'key_name', 'zone', 'monitoring', 'vpc_id', 'subnet_id', 'private_ip', 'ebs_optimized', 'name']

            clears = []
            for field in args.remove:
                fieldname = field.replace('-','_')
                if fieldname in fields:
                    clears.append("{0}=NULL")
            if len(clears):
                self.db.execute("update host_templates set {0} where template_id=%s".format(", ".join(clears)), (template_id, ))
                self.dbconn.commit()

            for tagname in args.remove_tag:
                self.db.execute("delete from host_template_tags where template_id=%s and `name`=%s", (template_id, tagname))
                self.dbconn.commit()

            for sg in args.remove_security_group:
                self.db.execute("delete from host_template_sg_associations where template_id=%s and security_group_id=%s", (template_id, sg))
                self.dbconn.commit()

            sets = []
            setvals = []
            for field in fields:
                val = getattr(args, field)
                if val is not None:
                    sets.append("{0}=%s".format(field))
                    setvals.append(val)
            if args.new_template_name:
                sets.append("template_name=%s")
                setvals.append(args.new_template_name)

            if len(sets):
                setvals.append(template_id)
                self.db.execute("update host_templates set {0} where template_id=%s".format(", ".join(sets)), setvals)
                self.dbconn.commit()

            for sg in args.security_group:
                self.db.execute("insert into host_template_sg_associations set template_id=%s, security_group_id=%s on duplicate key update security_group_id=%s",(template_id, sg, sg))
                self.dbconn.commit()
            for tagname, tagvalue in tags.iteritems():
                self.db.execute("insert into host_template_tags set template_id=%s, `name`=%s, `value`=%s on duplicate key update `value`=%s",(template_id, tagname, tagvalue, tagvalue))
                self.dbconn.commit()

            if len(sets) or len(tags) or len(args.security_group):
                self.logger.info("Template {0} updated".format(template_id))
            else:
                self.logger.info("No updates provided")



    def command_host_template_delete(self, args):
        template_id = args.template_id
        if args.template_name:
            self.db.execute("select template_id from host_templates where template_name=%s", (args.template_name, ))
            row = self.db.fetchone()
            if row:
                template_id = row[0]
            else:
                self.logger.error("Template {0} not found".format(args.template_name))

        if template_id:
            self.db.execute("delete from host_templates where template_id=%s", (template_id, ))
            self.db.execute("delete from host_template_tags where template_id=%s", (template_id, ))
            self.db.execute("delete from host_template_sg_associations where template_id=%s", (template_id, ))
            self.dbconn.commit()
            self.logger.info("Template {0} deleted".format(template_id))


    def __command_parse_tags(self, command_tag_list):
        tags = {}
        if command_tag_list:
            for tag in command_tag_list:
                parts = tag.split('=')
                if len(parts) != 2:
                    self.logger.error("Tag {0} not in the form tagname=tagvalue".format(tag))
                    return None
                tags[parts[0].strip()] = parts[1].strip()
        return tags

    def command_host_create(self, args):
        tags = self.__command_parse_tags(args.tag)
        # if there was an error parsing tags, then it will be None here
        if tags is None:
            return

        template_data = None
        template_id = args.template_id
        if args.template_name:
            self.db.execute("select template_id from host_templates where template_name=%s", (args.template_name, ))
            row = self.db.fetchone()
            if row:
                template_id = row[0]
            else:
                self.logger.error("Template {0} not found".format(args.template_name))
                return

        if template_id:
            self.db.execute("select region, instance_type, ami_id, key_name, zone, monitoring, vpc_id, subnet_id, private_ip, ebs_optimized, `name` from host_templates where template_id=%s", (template_id, ))
            row = self.db.fetchone()
            if not row:
                self.logger.error("Template {0} not found".format(template_id))
                return
            template_data = row

            self.db.execute("select security_group_id from host_template_sg_associations where template_id=%s", (template_id, ))
            sgrows = self.db.fetchall()

            self.db.execute("select `name`, `value` from host_template_tags where template_id=%s", (template_id, ))
            tagrows = self.db.fetchall()

            if sgrows:
                for sg in sgrows:
                    if sg not in args.security_group:
                        args.security_group.append(sg[0])
            if tagrows:
                for tagrow in tagrows:
                    if tagrow[0] not in tags:
                        tags[tagrow[0]] = tagrow[1]
            if template_data:
                cols = ['region', 'instance_type', 'ami_id', 'key_name', 'zone', 'monitoring', 'vpc_id', 'subnet_id', 'private_ip', 'ebs_optimized', 'name']
                col_id = 0
                for col in cols:
                    if template_data[col_id] is not None:
                        if getattr(args, col) is None:
                            setattr(args, col, template_data[col_id])
                    col_id += 1
        is_ok = True
        template_message = ''
        if template_id:
            template_message = ' or defined in template'
        if args.region is None:
            self.logger.error("--region must be provided as an option{0}".format(template_message))
            is_ok = False
        if args.ami_id is None:
            self.logger.error("--ami-id must be provided as an option{0}".format(template_message))
            is_ok = False
        if args.instance_type is None:
            self.logger.error("instance-type must be provided as an option{0}".format(template_message))
            is_ok = False

        if not is_ok:
            self.logger.error("No instance created")
            return

        if args.name:
            tags['Name'] = args.name

        self.create_instance(region=args.region, ami_id=args.ami_id, instance_type=args.instance_type, number=args.number, keypair=args.key_name, zone=args.zone, monitoring=args.monitoring, vpc_id=args.vpc_id, subnet_id=args.subnet_id, private_ip=args.private_ip, security_groups=args.security_group, ebs_optimized=args.ebs_optimized, tags=tags)


    def command_amilist(self, args):
        wheres = []
        wherevars = []
        if args.region:
            wheres.append("region=%s")
            wherevars.append(args.region)
        where = ''
        if wheres:
            where = 'where ' + " and ".join(wheres)

        sql = "select ami_id, region, name, architecture, virtualization_type, sriov_net_support, description from amis {0} order by region, ami_id".format(where)
        self.db.execute(sql, wherevars)
        rows = self.db.fetchall()
        if not rows:
            rows = []
        headers = ['AMI ID', 'Region', 'Name', 'Arch', 'Virt Type', 'Enh. Ntwrk', 'description']
        self.output_formatted("AMIs", headers, rows)

    def command_key(self, args):
        if args.command == 'list':
            where = ''
            wherevars = []
            if args.region:
                where = 'where region=%s'
                wherevars.append(args.region)
            self.db.execute("select region, key_name, fingerprint from key_pairs {0}".format(where), wherevars)
            rows = self.db.fetchall()
            if not rows:
                rows = []
            headers = ['region', 'key_name', 'fingerprint']
            self.output_formatted("Key Pairs", headers, rows, None, 1)


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
                    if last_instance_id and self.settings.HUMAN_OUTPUT:
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
        qryvars = []
        order_by = ''
        if args.search_field:
            if args.field_value:
                whereclauses.append("{0} = %s".format(args.search_field))
                qryvars.append(args.field_value)
            elif args.like:
                whereclauses.append("{0} like %s".format(args.search_field))
                qryvars.append('%' + args.like + '%')
            elif args.prefix:
                whereclauses.append("{0} like %s".format(args.search_field))
                qryvars.append(args.prefix + '%')
            order_by = ' order by {0}'.format(args.search_field)
        if args.zone:
            whereclauses.append("availability_zone like %s")
            qryvars.append(args.zone)
            if not order_by:
                order_by = ' order by availability_zone'

        if args.all:
            pass
        elif args.terminated:
            whereclauses.append("`terminated` = 1")
        else:
            whereclauses.append("`terminated` = 0")

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
                    filterclauses.append("sum(t.name = %s and t.value {0} %s) {1} 0".format(operator, sumoperator))
                    filtervals.append(tagname)
                    filtervals.append(prewild + tagvalue + postwild)

            if len(filtervals):
                qryvars += filtervals
                filterclause = "having " + " and ".join(filterclauses)

        if len(whereclauses):
            whereclause = "where " + " and ".join(whereclauses)
        else:
            whereclause = ""
        headers = ["Hostname", "instance_id", "availability_zone", "name", "private ip", "public ip", "vpc_id", 'subnet_id']
        cols = ['h.host', 'instance_id', 'availability_zone', 'h.name', 'h.ip_internal', 'h.ip_external', 'h.vpc_id', 'h.subnet_id']

        if args.extended:
            cols.append("case `terminated` when 0 then 'no' when 1 then 'yes' end")
            headers.append("term")

        if args.show_tags:
            cols.append("group_concat(concat(t.name,'=',t.value) SEPARATOR '\n')")
            headers.append('tags')

        sql = "select {0} from hosts h left join tags t on t.resource_id = h.instance_id {1} group by h.instance_id {2} {3}".format(", ".join(cols), whereclause, filterclause, order_by)

        self.db.execute(sql, qryvars)
        results = self.db.fetchall()

        self.output_formatted("Hosts", headers, results, insert_breaks=1)


    def command_host_add(self, args):
        self.logger.warn("host add command is deprecated and will soon be removed")
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
