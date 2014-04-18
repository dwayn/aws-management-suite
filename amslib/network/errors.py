__author__ = 'dwayn'

class NetworkManagerError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class ResourceNotFound(NetworkManagerError):
    pass

class Route53Error(NetworkManagerError):
    pass

class ResourceNotAvailable(NetworkManagerError):
    pass


