__author__ = 'dwayn'


class SshManagerError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class NotConnected(SshManagerError):
    pass

class FailedAuthentication(SshManagerError):
    pass




