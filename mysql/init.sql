-- Create the filesystem database
CREATE DATABASE IF NOT EXISTS filesystem;

-- Switch to the filesystem database
USE filesystem;

-- Create the directories table
CREATE TABLE directories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    parent_id INT DEFAULT NULL,
    FOREIGN KEY (parent_id) REFERENCES directories (id) ON DELETE CASCADE
);

-- Create the files table
CREATE TABLE files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    parent_id INT,
    size INT DEFAULT 0,
    content LONGBLOB,
    FOREIGN KEY (parent_id) REFERENCES directories (id) ON DELETE CASCADE
);

-- Create the file_locks table
CREATE TABLE file_locks (
    file_id INT PRIMARY KEY,
    locked_by VARCHAR(255),
    locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files (id)
);