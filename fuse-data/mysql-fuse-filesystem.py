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
SCHEMA_SETUP_FILES = """
CREATE TABLE IF NOT EXISTS files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    path VARCHAR(255) UNIQUE NOT NULL,
    mode INT NOT NULL,
    nlink INT NOT NULL,
    size INT NOT NULL DEFAULT 0,
    ctime FLOAT NOT NULL,
    mtime FLOAT NOT NULL,
    atime FLOAT NOT NULL,
    data LONGBLOB
);
"""
SCHEMA_SETUP_LOCKS = """
CREATE TABLE IF NOT EXISTS locks (
    path VARCHAR(255) PRIMARY KEY, -- The file path being locked
    locked_by VARCHAR(255) NOT NULL, -- Identifier of the lock owner (e.g., process, user)
    lock_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Time when the file was locked
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
        self.cursor.execute(SCHEMA_SETUP_FILES)
        self.cursor.execute(SCHEMA_SETUP_LOCKS)
        self.conn.reset_session()
        self.conn.commit()

        # Ensure root directory exists
        self.cursor.execute("SELECT * FROM files WHERE path = '/'")
        if not self.cursor.fetchone():
            now = time()
            self.cursor.execute(
                """
                INSERT INTO files (path, mode, nlink, size, ctime, mtime, atime)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                ('/', S_IFDIR | 0o755, 2, 0, now, now, now)
            )
            self.conn.commit()
            
    def getattr(self, path, fh=None):
        self.cursor.execute("SELECT * FROM files WHERE path = %s", (path,))
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
        
        self.cursor.execute("SELECT * FROM files WHERE path = %s", (path,))
        if self.cursor.fetchone():
            raise FuseOSError(errno.EEXIST)  # Directory already exists
        
        # Get the parent directory
        parent_dir = os.path.dirname(path)
        self.cursor.execute("SELECT * FROM files WHERE path = %s", (parent_dir,))
        if not self.cursor.fetchone():
            raise FuseOSError(errno.ENOENT)
        
        now = time()
        try:
            self.cursor.execute(
                """
                INSERT INTO files (path, mode, nlink, size, ctime, mtime, atime)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (path, S_IFDIR | mode, 2, 0, now, now, now)
            )
            # Increment link count for the parent directory
            self.cursor.execute("UPDATE files SET nlink = nlink + 1 WHERE path = %s", (parent_dir,))
            self.conn.commit()
            
            print(f"New directory created: {path}, parent directory link count updated.")
        except mysql.connector.Error as e:
            raise FuseOSError(errno.EEXIST)
        
    def readdir(self, path, fh):
        print(f"readdir called with path={path}")
        self.cursor.execute("SELECT path FROM files WHERE path LIKE %s", (path.rstrip('/') + '/%',))
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

    def create(self, path, mode):
        print(f"cat called with path={path}, mode={oct(mode)}")
        
        self.cursor.execute("SELECT * FROM files WHERE path = %s", (path,))
        if self.cursor.fetchone():
            raise FuseOSError(errno.EEXIST)  # File already exists
        
        parent_dir = os.path.dirname(path)
        self.cursor.execute("SELECT * FROM files WHERE path = %s", (parent_dir,))
        if not self.cursor.fetchone():
            raise FuseOSError(errno.ENOENT)

        now = time()
        try:
            self.cursor.execute(
                """
                INSERT INTO files (path, mode, nlink, size, ctime, mtime, atime)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (path, S_IFREG | mode, 1, 0, now, now, now)
            )
            self.cursor.execute("UPDATE files SET nlink = nlink + 1 WHERE path = %s", (parent_dir,))
            self.conn.commit()
            print(f"New file created: {path}, parent directory link count updated.")
        except mysql.connector.Error as e:
            raise FuseOSError(errno.EEXIST)
        return 0
    
    def unlink(self, path):
        print(f"unlink called with path={path}")
        
        self.cursor.execute("SELECT * FROM files WHERE path = %s", (path,))
        entry = self.cursor.fetchone()
        if not entry:
            raise FuseOSError(errno.ENOENT)

        parent_dir = os.path.dirname(path.rstrip('/'))
        self.cursor.execute("SELECT * FROM files WHERE path = %s", (parent_dir,))
        if not self.cursor.fetchone():
            raise FuseOSError(errno.ENOENT)
            
        try:
            # Delete the file
            self.cursor.execute("DELETE FROM files WHERE path = %s", (path,))
            # Decrement the parent directory's nlink
            self.cursor.execute("UPDATE files SET nlink = nlink - 1 WHERE path = %s", (parent_dir,))
            self.conn.commit()
        except mysql.connector.Error as e:
            self.conn.rollback()
            raise FuseOSError(errno.EIO)
    
    def rmdir(self, path):
        print(f"rmdir called with path={path}")
        
        self.cursor.execute("SELECT * FROM files WHERE path = %s", (path,))
        entry = self.cursor.fetchone()
        if not entry:
            raise FuseOSError(errno.ENOENT)

        parent_dir = os.path.dirname(path.rstrip('/'))
        self.cursor.execute("SELECT * FROM files WHERE path = %s", (parent_dir,))
        if not self.cursor.fetchone():
            raise FuseOSError(errno.ENOENT)
        
        # Check if the directory is empty
        self.cursor.execute("SELECT * FROM files WHERE path LIKE %s", (path.rstrip('/') + '/%',))
        if self.cursor.fetchone():
            raise FuseOSError(errno.ENOTEMPTY)

        self.cursor.execute("DELETE FROM files WHERE path = %s", (path,))
        parent_dir = os.path.dirname(path)
        self.cursor.execute("UPDATE files SET nlink = nlink - 1 WHERE path = %s", (parent_dir,))
        self.conn.commit()
        
    def write(self, path, data, offset, fh):
        print(f"write called with path={path}, offset={offset}")
        self.cursor.execute("SELECT * FROM files WHERE path = %s", (path,))
        entry = self.cursor.fetchone()
        if not entry:
            raise FuseOSError(errno.ENOENT)

        # Handle writing the data
        current_data = entry['data'] or b''  # Retrieve current data, default to empty if None
        new_data = current_data[:offset] + data + current_data[offset + len(data):]

        # Update file size and data
        new_size = len(new_data)
        try:
            self.cursor.execute(
                """
                UPDATE files SET size = %s, data = %s, mtime = %s WHERE path = %s
                """,
                (new_size, new_data, time(), path)
            )
            self.conn.commit()
        except mysql.connector.Error as e:
            self.conn.rollback()
            raise FuseOSError(errno.EIO)

        return len(data)
    
    def truncate(self, path, length, fh=None):
        self.cursor.execute("SELECT * FROM files WHERE path = %s", (path,))
        entry = self.cursor.fetchone()
        if not entry:
            raise FuseOSError(errno.ENOENT)

        data = entry['data'] or b''
        truncated_data = data[:length]

        self.cursor.execute(
            """
            UPDATE files SET size = %s, data = %s, mtime = %s WHERE path = %s
            """,
            (length, truncated_data, time(), path)
        )
        self.conn.commit()
        
    def read(self, path, size, offset, fh):
        print(f"read called with path={path}, offset={offset}")
        self.cursor.execute("SELECT * FROM files WHERE path = %s", (path,))
        entry = self.cursor.fetchone()
        if not entry:
            raise FuseOSError(errno.ENOENT)

        data = entry['data'] or b''
        return data[offset:offset + size]
        
    def is_locked(self, path):
        """Check if the file is locked."""
        self.cursor.execute("SELECT * FROM locks WHERE path = %s", (path,))
        return self.cursor.fetchone() is not None

    def lock_file(self, path, locker):
        """Lock the file for editing."""
        if self.is_locked(path):
            raise FuseOSError(errno.EACCES)  # File is already locked
        
        try:
            self.cursor.execute(
                "INSERT INTO locks (path, locked_by) VALUES (%s, %s)",
                (path, locker)
            )
            self.conn.commit()
        except mysql.connector.Error as e:
            raise FuseOSError(errno.EIO)

    def unlock_file(self, path, locker):
        """Unlock the file."""
        self.cursor.execute("SELECT * FROM locks WHERE path = %s", (path,))
        lock = self.cursor.fetchone()

        if not lock:
            raise FuseOSError(errno.ENOENT)  # File not locked
        
        if lock['locked_by'] != locker:
            raise FuseOSError(errno.EPERM)  # Only the locker can unlock the file

        self.cursor.execute("DELETE FROM locks WHERE path = %s", (path,))
        self.conn.commit()
        
    def open(self, path, flags):
        locker = f"pid:{os.getpid()}"  # Use process ID as the locker identifier

        if flags & os.O_WRONLY or flags & os.O_RDWR:
            # If the file is being opened for writing
            if self.is_locked(path):
                raise FuseOSError(errno.EACCES)  # Deny access if locked
            self.lock_file(path, locker)  # Lock the file for writing
        
        return 0  # Return a dummy file handle

    def release(self, path, fh):
        locker = f"pid:{os.getpid()}"  # Use process ID as the locker identifier
        try:
            self.unlock_file(path, locker)  # Unlock the file
        except FuseOSError:
            pass  # Ignore errors (file might not be locked)
        return 0

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 mysql-fuse-filesystem.py <mountpoint>")
        sys.exit(1) # Non-zero indicates failure
    mountpoint = sys.argv[1]
    # mountpoint = '/mnt/vfs'
    
    try:
        # Initialize FUSE
        print("Starting FUSE...")
        fuse = FUSE(MySQLFuse(), mountpoint, nothreads=True, foreground=True, allow_other=True)
        print("FUSE started successfully.")
        sys.exit(0)  # Exit with 0 to indicate success
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(2)  # Non-zero for failure
        
if __name__ == '__main__':
    main()
    