__author__ = 'dwayn'

class StorageManagerError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class InstanceNotFound(StorageManagerError):
    pass

class VolumeNotAvailable(StorageManagerError):
    pass

class VolumeGroupNotFound(StorageManagerError):
    pass

class RaidError(StorageManagerError):
    pass

class VolumeMountError(StorageManagerError):
    pass

class SnapshotError(StorageManagerError):
    pass

class SnapshotCreateError(SnapshotError):
    pass

class SnapshotScheduleError(SnapshotError):
    pass

class SnapshotNotFound(SnapshotError):
    pass


