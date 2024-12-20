-- Create the filesystem database
CREATE DATABASE IF NOT EXISTS filesystem;

-- Switch to the filesystem database
USE filesystem;

-- Create the files table
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

-- Create the locks table
CREATE TABLE IF NOT EXISTS locks (
    path VARCHAR(255) PRIMARY KEY, -- The file path being locked
    locked_by VARCHAR(255) NOT NULL, -- Identifier of the lock owner (e.g., process, user)
    lock_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Time when the file was locked
);