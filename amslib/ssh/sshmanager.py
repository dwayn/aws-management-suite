__author__ = 'dwayn'
import paramiko
import socket
import pipes
from errors import *


class SSHManager:

    def __init__(self):
        self.client = paramiko.SSHClient()
        self.hostname = None
        self.__connected = False


    # connect to a host
    def connect(self, hostname, port=22, username=None, password=None, key_filename=None, timeout=None, look_for_keys=True):
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(hostname=hostname, port=port, username=username, password=password, key_filename=key_filename, timeout=timeout, look_for_keys=look_for_keys)
        self.hostname = hostname
        self.__connected = True


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

