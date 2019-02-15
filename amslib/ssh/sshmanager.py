__author__ = 'dwayn'
import paramiko
import socket
import pipes
from errors import *
import pymysql.cursors


class SSHManager:

    def __init__(self, settings):
        self.client = paramiko.SSHClient()
        self.hostname = None
        self.__connected = False
        self.instance = None
        self.dbconn = None
        self.db = None
        self.settings = settings


    # connect to a host
    def connect(self, hostname, port=22, username=None, password=None, key_filename=None, timeout=None, look_for_keys=True):
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(hostname=hostname, port=port, username=username, password=password, key_filename=key_filename, timeout=timeout, look_for_keys=look_for_keys)
        self.hostname = hostname
        self.__connected = True

    def connect_instance(self, instance, port=22, username=None, password=None, key_filename=None, timeout=None, look_for_keys=True):
        if not self.db:
            self.dbconn = pymysql.connect(host=self.settings.TRACKING_DB['host'],
                             port=self.settings.TRACKING_DB['port'],
                             user=self.settings.TRACKING_DB['user'],
                             password=self.settings.TRACKING_DB['pass'],
                             db=self.settings.TRACKING_DB['dbname'])
            self.db = self.dbconn.cursor()

        self.db.execute("select ip_internal, ip_external, vpc_id, subnet_id from hosts where instance_id=%s", (instance, ))
        data = self.db.fetchone()
        if not data:
            raise InstanceNotFound("Instance ID {0} not found".format(instance))

        ip_internal, hostname_external, vpc_id, subnet_id = data

        hostname = None
        instance_domain = 'Unknown'
        if subnet_id:
            hostname = ip_internal
            instance_domain = 'VPC'
        else:
            # use the ec2 external hostname for ec2 classic hosts because it will map to the internal ip address when
            #   run from within ec2 and will map to external ip when run from outside of ec2
            hostname = hostname_external
            instance_domain = 'EC2 Classic'

        if not hostname:
            raise InstanceNotAccessible("Unable to determine an IP address in {0} for instance ID: {1}".format(instance_domain, instance))

        return self.connect(hostname=hostname, port=port, username=username, password=password, key_filename=key_filename, timeout=timeout, look_for_keys=look_for_keys)


    def run(self, command):
        if not self.__connected:
            raise NotConnected("Not currently connected to a host: see sshmanager.connect()")
        stdin, stdout, stderr = self.client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()

        return ("".join(stdout.readlines()), "".join(stderr.readlines()), exit_code)


    def sudo(self, command, sudo_password):
        channel_buffer_size = 4096
        chan = self.client.get_transport().open_session()
        # print type(chan)
        chan.get_pty(term='TERM', width=0, height=0)

        sudo_output = ''
        try:
            cmd = 'sudo -k && sudo -S -p "[AMS sudo] enter password: " -u root /bin/sh -c {0}'.format(pipes.quote('echo "AMS-SUDO-SUCCESS"; {0}'.format(command)))
            chan.exec_command(cmd)
            while not sudo_output.endswith("[AMS sudo] enter password: ") and "AMS-SUDO-SUCCESS" not in sudo_output:
                chunk = chan.recv(channel_buffer_size)
                if not chunk:
                    raise SshManagerError('ssh connection closed waiting for password prompt')

                sudo_output += chunk
                if "AMS-SUDO-SUCCESS" not in sudo_output:
                    chan.sendall(sudo_password + '\n')
        except socket.timeout:
            raise SshManagerError('ssh timed out waiting for sudo.\n' + sudo_output)
        stdout = chan.makefile('rb', channel_buffer_size).readlines()
        ix = 0
        # trims the
        for i in range(0, len(stdout)):
            if "AMS-SUDO-SUCCESS" in stdout[i]:
                ix = i + 1
        if ix >= len(stdout):
            ix = 0
        stdout = "".join(stdout[ix:])
        stderr = ''.join(chan.makefile_stderr('rb', channel_buffer_size))

        return (stdout, stderr, chan.recv_exit_status())

