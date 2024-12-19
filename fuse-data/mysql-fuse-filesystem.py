import os
from fuse import FUSE, FuseOSError, Operations
from stat import S_IFDIR, S_IFREG
import errno

class MySQLFuse(Operations):
    def __init__(self):
        self.files = {}
        self.data = {}

    def getattr(self, path, fh=None):
        if path == '/':
            # Attributes for the root directory
            st = {
                'st_mode': (S_IFDIR | 0o755),
                'st_nlink': 2,
                'st_size': 0,
                'st_ctime': 0,
                'st_mtime': 0,
                'st_atime': 0,
            }
        elif path in self.files:
            # Attributes for files
            st = {
                'st_mode': (S_IFREG | 0o644),
                'st_nlink': 1,
                'st_size': len(self.data.get(path, b'')),
                'st_ctime': 0,
                'st_mtime': 0,
                'st_atime': 0,
            }
        else:
            raise FuseOSError(errno.ENOENT)

        return st

    def mkdir(self, path, mode):
        # Add directory to the list of known paths
        self.files[path] = {'type': 'dir'}
        self.files[path]['st_mode'] = (S_IFDIR | mode)
        self.files[path]['st_nlink'] = 2

    def create(self, path, mode):
        # Add file to the list of known paths
        self.files[path] = {'type': 'file'}
        self.files[path]['st_mode'] = (S_IFREG | mode)
        self.files[path]['st_nlink'] = 1
        self.data[path] = b''

# Initialize FUSE
fuse = FUSE(MySQLFuse(), '/mnt/myfuse', foreground=True)
