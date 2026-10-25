-- Run once on an existing rqms_db (phpMyAdmin) before using Account Handler.
USE rqms_db;

ALTER TABLE users
  MODIFY COLUMN password VARCHAR(255) NOT NULL,
  ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1;
