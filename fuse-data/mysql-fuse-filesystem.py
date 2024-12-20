import os
from fuse import FUSE, FuseOSError, Operations
from stat import S_IFDIR, S_IFREG
import mysql.connector
import errno
import sys
from time import time

# MySQL Configuration
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'Test.123'),
    'database': os.getenv('MYSQL_DATABASE', 'filesystem'),
    'port': int(os.getenv('MYSQL_PORT', 3306))
}

# SQL schema setup
SCHEMA_SETUP = """
CREATE TABLE IF NOT EXISTS filesystem (
    id INT AUTO_INCREMENT PRIMARY KEY,
    path VARCHAR(255) UNIQUE NOT NULL,
    mode INT NOT NULL,
    nlink INT NOT NULL,
    size INT NOT NULL DEFAULT 0,
    ctime FLOAT NOT NULL,
    mtime FLOAT NOT NULL,
    atime FLOAT NOT NULL
);
"""

class MySQLFuse(Operations):
    def __init__(self):
        self.files = {'/': {'st_mode': (S_IFDIR | 0o755), 'st_nlink': 2}}  # Initialize root directory
        self.data = {}
        self.conn = mysql.connector.connect(**DB_CONFIG)
        self.cursor = self.conn.cursor(dictionary=True)
        self._initialize_schema()

    def _initialize_schema(self):
        self.cursor.execute(SCHEMA_SETUP)
        self.conn.commit()

        # Ensure root directory exists
        self.cursor.execute("SELECT * FROM filesystem WHERE path = '/'")
        if not self.cursor.fetchone():
            now = time()
            self.cursor.execute(
                """
                INSERT INTO filesystem (path, mode, nlink, size, ctime, mtime, atime)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                ('/', S_IFDIR | 0o755, 2, 0, now, now, now)
            )
            self.conn.commit()
            
    def getattr(self, path, fh=None):
        self.cursor.execute("SELECT * FROM filesystem WHERE path = %s", (path,))
        entry = self.cursor.fetchone()
        if not entry:
            raise FuseOSError(errno.ENOENT)
        return {
            'st_mode': entry['mode'],
            'st_nlink': entry['nlink'],
            'st_size': entry['size'],
            'st_ctime': entry['ctime'],
            'st_mtime': entry['mtime'],
            'st_atime': entry['atime']
        }

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
        self.cursor.execute("SELECT path FROM filesystem WHERE path LIKE %s", (path.rstrip('/') + '/%',))
        entries = self.cursor.fetchall()
        print(f'entries: {entries}')
        if path == '/':
            # List the top-level directories (root)
            dir_contents = ['.', '..']
            for entry_dict in entries:
                entry = entry_dict['path']
                # if entry != '/':  # Don't add the root itself
                if entry != '/' and os.path.dirname(entry) == '/':  # Only include entries directly in '/'
                    print(f'entry: {entry}')
                    dir_contents.append(os.path.basename(entry))  # List entries in root
            print(f"Root directory contents: {dir_contents}")
            return dir_contents
        
        # If path is a directory, list its contents
        dir_contents = ['.', '..']
        for entry_dict in entries:
            entry = entry_dict['path']
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
    