-- Run once on an existing rqms_db (phpMyAdmin).
USE rqms_db;

ALTER TABLE queue_patients
  ADD COLUMN reminder_status VARCHAR(20) DEFAULT 'Not Sent',
  ADD COLUMN reminder_sent_at DATETIME NULL,
  ADD COLUMN turn_notification_status VARCHAR(20) DEFAULT 'Not Sent',
  ADD COLUMN turn_notification_sent_at DATETIME NULL;
