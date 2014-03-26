__author__ = 'dwayn'
import ssh
import time
import uuid
from errors import *


class SSHManager:

    def __init__(self):
        self.__client = ssh.SSHClient()
        self.__stderr_fname = "/tmp/ams_err_{0}".format(uuid.uuid4())
        self.__exit_code_fname = "/tmp/ams_xc_{0}".format(str(uuid.uuid4()))
        self.__marker = str(uuid.uuid4())
        self.__finish_marker = str(uuid.uuid4())
        self.__command_append = " 2> {0}  #---start_output-{1}--\necho $? > {2}\n".format(self.__stderr_fname, self.__marker, self.__exit_code_fname)
        self.__run_channel = None
        self.__sudo_channel = None
        self.__connected = False

    # connect to a host
    def connect(self, hostname, port=22, username=None, password=None, key_filename=None, timeout=None, look_for_keys=True):
        self.__client.set_missing_host_key_policy(ssh.AutoAddPolicy())
        self.__client.connect(hostname=hostname, port=port, username=username, password=password, key_filename=key_filename, timeout=timeout, look_for_keys=look_for_keys)
        self.__connected = True
        if self.__run_channel:
            self.__run_channel.close()
            self.__run_channel = None
        if self.__sudo_channel:
            self.__sudo_channel.close()
            self.__sudo_channel = None


    # returns a tuple (str, str, str) -> (stdout, stderr, exit code)
    def run(self, command):
        if not self.__connected:
            raise NotConnected("Not currently connected to a host: see sshmanager.connect()")
        if not self.__run_channel:
            self.__run_channel = self.__client.invoke_shell()
            self.__create_end_marker_script(self.__run_channel, '/tmp/ams_run_end_marker')
        return self.__runcommand(channel=self.__run_channel, command=command, marker_script='/tmp/ams_run_end_marker')


    # returns a tuple (str, str, str) -> (stdout, stderr, exit code)
    def sudo(self, command, sudo_password=None):
        if not self.__connected:
            raise NotConnected("Not currently connected to a host: see sshmanager.connect()")
        if not self.__sudo_channel:
            self.__sudo_channel = self.__client.invoke_shell()
            self.__auth_sudo(self.__sudo_channel, sudo_password)
            self.__create_end_marker_script(self.__sudo_channel, '/tmp/ams_sudo_end_marker')
        return self.__runcommand(channel=self.__sudo_channel, command=command, marker_script='/tmp/ams_sudo_end_marker')

    def __create_end_marker_script(self, channel, filename):
        channel.send("echo '#!/bin/bash\necho {0}' > {1}\n chmod +x {1}\n{1}\n".format(self.__finish_marker, filename))
        time.sleep(0.2)
        res = ''
        while not channel.recv_ready():
            time.sleep(0.1)
        while channel.recv_ready() or res.count(self.__finish_marker) < 2:
            res += channel.recv(1024)
            time.sleep(0.1)
        self.__flush_output_buffer(channel)

    def __runcommand(self, channel, command, marker_script):
        self.__flush_output_buffer(channel)

        running_command = command.strip() + self.__command_append + marker_script + "\n"
        channel.send(running_command)
        res = ''
        time.sleep(0.2)
        while not channel.recv_ready():
            time.sleep(0.1)
        while channel.recv_ready() or not self.__finish_marker in res:
            res += channel.recv(1024)
            time.sleep(0.1)
        stdout = res.splitlines()

        #print stdout
        target_id = 0
        for x in range(len(stdout) - 1, -1, -1):
            if self.__marker in stdout[x]:
                target_id = x + 1
                break
        end_id = len(stdout)
        for x in range(len(stdout) - 1, -1, -1):
            prefix = self.__exit_code_fname[0:25]
            if prefix in stdout[x]:
                end_id = x
        #print target_id, end_id
        if target_id >= end_id:
            stdout = ''
        else:
            stdout = '\n'.join(stdout[target_id:end_id])

        #print '---------------------------------------------------------------------'
        #print stdout
        #print '---------------------------------------------------------------------'

        stderr, exit_code = self.__get_exit_code_and_stderr(channel)
        return (stdout, stderr, exit_code)

    def __flush_output_buffer(self, channel):
        time.sleep(0.2)
        while channel.recv_ready():
            # clear the buffer
            channel.recv(1024)
            time.sleep(0.1)


    # returns tuple (stderr, exit code)
    def __get_exit_code_and_stderr(self, channel):
        self.__flush_output_buffer(channel)
        channel.send('cat {0}\n'.format(self.__stderr_fname))
        res = ''
        time.sleep(0.2)
        while not channel.recv_ready():
            time.sleep(0.1)
        while channel.recv_ready():
            res += channel.recv(1024)
            time.sleep(0.1)
        stderr = res.splitlines()
        prefix = self.__stderr_fname[0:25]
        start_id = 0
        for x in range(len(stderr) - 1, -1, -1):
            if prefix in stderr[x]:
                start_id = x + 1
                break
        # strip the first and last line terminal prompts
        stderr = stderr[start_id: len(stderr) - 1]
        stderr = '\n'.join(stderr)
        #print stderr

        #print "EXIT CODE----------"
        channel.send('cat {0}\n'.format(self.__exit_code_fname))
        res = ''
        time.sleep(0.2)
        while not channel.recv_ready():
            time.sleep(0.1)
        while channel.recv_ready():
            res += channel.recv(1024)
            # increased the delay here as sometimes this is a bit slow to return (need to look into this
            time.sleep(1)

        #TODO fix this annoying hack that is a workaround for flakiness in how fast stdout is streamed
        code = res.splitlines()
        if len(code) <= 2: # we haven't received all the expected lines back
            while not channel.recv_ready():
                time.sleep(0.1)
            while channel.recv_ready():
                res += channel.recv(1024)
                # increased the delay here as sometimes this is a bit slow to return (need to look into this
                time.sleep(1)
        code = res.splitlines()

        start_id = 0
        for x in range(len(code) - 1, -1, -1):
            if self.__exit_code_fname in code[x]:
                start_id = x + 1
                break
        code = code[start_id]
        #print code
        channel.send("rm -f {0} {1}\n".format(self.__exit_code_fname, self.__stderr_fname))
        time.sleep(0.2)
        while not channel.recv_ready():
            time.sleep(0.1)
        self.__flush_output_buffer(channel)

        return (stderr, code)


    def __auth_sudo(self, channel, sudo_password=None):
        self.__flush_output_buffer(channel)

        channel.send("sudo su -\n")
        time.sleep(0.2)
        while not channel.recv_ready():
            #print "Waiting for root challenge..."
            time.sleep(0.1)
        res = ''
        while channel.recv_ready():
            res += channel.recv(1024)
            time.sleep(0.1)
        lines = res.splitlines()
        #print '-------------------------------------'
        #print lines[len(lines) - 1]
        #print '-------------------------------------'
        if lines[len(lines) - 1] == "Password:":
            channel.send("%s\n" % sudo_password)
            time.sleep(0.2)
            while not channel.recv_ready():
                #print "Authenticating..."
                time.sleep(0.1)
            res = ''
            while channel.recv_ready():
                res += channel.recv(1024)
            lines = res.splitlines()
            #print "------------------------------------------------------"
            #print lines[len(lines) - 1]
            #print "------------------------------------------------------"
            if lines[len(lines) - 1] == "Password:":
                raise FailedAuthentication("Failed Sudo Authentication, check the sudo password")

        self.__flush_output_buffer(channel)



