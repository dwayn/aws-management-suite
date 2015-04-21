__author__ = 'dwayn'

class InstanceManagerError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class InstanceNotFound(InstanceManagerError):
    pass

class InvalidInstanceAction(InstanceManagerError):
    pass

