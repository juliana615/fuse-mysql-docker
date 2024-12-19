import os
from fuse import FUSE, FuseOSError, Operations
import mysql.connector
from stat import S_IFDIR, S_IFREG
import errno

# MySQL Configuration
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'Test.123'),
    'database': os.getenv('MYSQL_DATABASE', 'filesystem'),
    'port': int(os.getenv('MYSQL_PORT', 3306))
}


class MySQLFuse(Operations):
    def __init__(self, root):
        self.files = {}
        self.data = {}
        self.conn = mysql.connector.connect(**DB_CONFIG)
        self.cursor = self.conn.cursor(dictionary=True)
        self.root = root

    def _full_path(self, partial):
        # Virtual filesystem, no local path interaction is required
        return self.root+partial

    def readdir(self, path, fh):
        try:
            print("==== readdir called for path:", path)
            parent_id = self._get_dir_id(path)

            self.cursor.execute("SELECT * FROM directories")
            print("Hello: ", self.cursor.fetchall())

            self.cursor.execute(
                "SELECT * FROM directories WHERE parent_id IS %s", (
                    parent_id,)
            )
            dirs = [row['name'] for row in self.cursor.fetchall()]
            self.cursor.execute(
                "SELECT * FROM files WHERE parent_id IS %s", (parent_id,)
            )
            files = [row['name'] for row in self.cursor.fetchall()]
            return ['.', '..'] + dirs + files
        except Exception as e:
            print("readdir error: ", e)
            return 0

    # def getattr(self, path, fh=None):
    #     print("==== getattr called for path:", path)
    #     if path == '/':
    #         return {'st_mode': (0o40755), 'st_nlink': 2}

    #     parent_id, name = self._get_parent_and_name(path)

    #     if self._is_dir(parent_id, name):
    #         return {'st_mode': (0o40755), 'st_nlink': 2}
    #     elif self._is_file(parent_id, name):
    #         file_info = self._get_file_info(parent_id, name)
    #         return {'st_mode': (0o100644), 'st_size': file_info['size'], 'st_nlink': 1}
    #     else:
    #         raise FileNotFoundError(f"File or directory '{path}' not found")

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
    
    def read(self, path, size, offset, fh):
        parent_id, name = self._get_parent_and_name(path)
        self.cursor.execute(
            "SELECT content FROM files WHERE parent_id = %s AND name = %s", (
                parent_id, name)
        )
        row = self.cursor.fetchone()
        return row['content'][offset:offset+size] if row else b''

    def write(self, path, data, offset, fh):
        parent_id, name = self._get_parent_and_name(path)
        self.cursor.execute(
            "SELECT content FROM files WHERE parent_id = %s AND name = %s", (
                parent_id, name)
        )
        row = self.cursor.fetchone()
        content = row['content'] if row else b''
        new_content = content[:offset] + data + content[offset + len(data):]
        self.cursor.execute(
            "UPDATE files SET content = %s, size = %s WHERE parent_id = %s AND name = %s",
            (new_content, len(new_content), parent_id, name)
        )
        self.conn.commit()
        return len(data)

    def mkdir(self, path, mode):
        try:
            print("==== mkdir called for path:", path)
            parent_id, name = self._get_parent_and_name(path)
            full_path = self._full_path(path)
            print("Resolved full path for mkdir:", full_path)

            # Insert into database
            self.cursor.execute(
                "INSERT INTO directories (name, parent_id) VALUES (%s, %s)", (name, parent_id))
            self.conn.commit()

            # Ensure the full path is valid
            if not os.path.exists(os.path.dirname(full_path)):
                raise FileNotFoundError(
                    f"Base path does not exist: {os.path.dirname(full_path)}")

            # Attempt to create the directory
            # os.mkdir(full_path, 644)
            print("Directory created successfully.")
            return 0

        except Exception as e:
            print("Error in mkdir:", e)
            raise

    def unlink(self, path):
        print("==== unlink called for path:", path)
        parent_id, name = self._get_parent_and_name(path)
        self.cursor.execute(
            "DELETE FROM files WHERE parent_id = %s AND name = %s", (
                parent_id, name)
        )
        self.conn.commit()
        return 0

    def _get_dir_id(self, path):
        if path == '/':
            return None
        segments = path.strip('/').split('/')
        parent_id = None
        for segment in segments:
            self.cursor.execute(
                "SELECT id FROM directories WHERE name = %s AND parent_id = %s", (
                    segment, parent_id)
            )
            row = self.cursor.fetchone()
            if not row:
                raise FileNotFoundError(f"Directory '{segment}' not found")
            parent_id = row['id']
        return parent_id

    def _get_parent_and_name(self, path):
        segments = path.strip('/').split('/')
        name = segments[-1]
        parent_id = self._get_dir_id('/' + '/'.join(segments[:-1]))
        return parent_id, name

    def _is_dir(self, parent_id, name):
        self.cursor.execute(
            "SELECT id FROM directories WHERE parent_id = %s AND name = %s", (
                parent_id, name)
        )
        return self.cursor.fetchone() is not None

    def _is_file(self, parent_id, name):
        self.cursor.execute(
            "SELECT id FROM files WHERE parent_id = %s AND name = %s", (
                parent_id, name)
        )
        return self.cursor.fetchone() is not None

    def _get_file_info(self, parent_id, name):
        self.cursor.execute(
            "SELECT size FROM files WHERE parent_id = %s AND name = %s", (
                parent_id, name)
        )
        return self.cursor.fetchone()


if __name__ == '__main__':
    import sys
    # if len(sys.argv) < 2:
    #     print("Usage: python3 mysql-fuse-filesystem.py <mountpoint>")
    #     sys.exit(1)
    # mountpoint = sys.argv[1]
    mountpoint = '/mnt/virtual_fs'
    FUSE(MySQLFuse(mountpoint), mountpoint, nothreads=True, foreground=True, nonempty=True)
