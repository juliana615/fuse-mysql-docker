import os
from fuse import FUSE, FuseOSError, Operations
from stat import S_IFDIR, S_IFREG
import errno
import sys
from time import time

class MySQLFuse(Operations):
    def __init__(self):
        self.files = {'/': {'st_mode': (S_IFDIR | 0o755), 'st_nlink': 2}}  # Initialize root directory
        self.data = {}

    def getattr(self, path, fh=None):
        if path == '/':
            # Attributes for the root directory
            st = {
                'st_mode': (S_IFDIR | 0o755),
                'st_nlink': 2,
            }
        elif path in self.files:
            # Attributes for files
            st = self.files[path]
        else:
            raise FuseOSError(errno.ENOENT)

        return st

    def mkdir(self, path, mode):
        print(f"mkdir called with path={path}, mode={oct(mode)}")
        print(f"Current files: {self.files}")
        
        if path in self.files:
            raise FuseOSError(errno.EEXIST)  # Directory already exists
        
        # Get the parent directory
        parent_dir = os.path.dirname(path)
        if parent_dir not in self.files and parent_dir != '/':
            raise FuseOSError(errno.ENOENT)  # Parent directory does not exist
        
        now = time()
        # Add directory to the internal structure
        self.files[path] = {
            'st_mode': (S_IFDIR | mode),
            'st_nlink': 2,
            'st_size': 0,
            'st_ctime': now,
            'st_mtime': now,
            'st_atime': now,
        }
        
        # Update the parent directory's link count
        if parent_dir in self.files:
            self.files[parent_dir]['st_nlink'] += 1  # Increment link count for parent directory
        elif parent_dir == '/':  # If root directory, no need to increment further
            pass
        else:
            raise FuseOSError(errno.ENOENT)  # Parent directory doesn't exist
        
        print(f"New directory created: {path}, parent directory link count updated.")
        
    def readdir(self, path, fh):
        print(f"readdir called with path={path}")
        
        if path == '/':
            # List the top-level directories (root)
            dir_contents = ['.', '..']
            for entry in self.files:
                # if entry != '/':  # Don't add the root itself
                if entry != '/' and os.path.dirname(entry) == '/':  # Only include entries directly in '/'
                    print(f'entry: {entry}')
                    dir_contents.append(os.path.basename(entry))  # List entries in root
            print(f"Root directory contents: {dir_contents}")
            return dir_contents
        
        # If path is a directory, list its contents
        dir_contents = ['.', '..']
        for entry in self.files:
            if os.path.dirname(entry) == path:
                dir_contents.append(os.path.basename(entry))
        
        print(f"Contents of {path}: {dir_contents}")
        return dir_contents

def main():
    # if len(sys.argv) < 2:
    #     print("Usage: python3 mysql-fuse-filesystem.py <mountpoint>")
    #     sys.exit(1)
    # mountpoint = sys.argv[1]
    mountpoint = '/mnt/vfs'
    # Initialize FUSE
    fuse = FUSE(MySQLFuse(), mountpoint, foreground=True)
    
if __name__ == '__main__':
    main()
    