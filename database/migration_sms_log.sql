-- Run once on an existing rqms_db (phpMyAdmin).
USE rqms_db;

CREATE TABLE IF NOT EXISTS sms_notification_log (
  sms_log_id INT AUTO_INCREMENT PRIMARY KEY,
  queue_id INT NULL,
  patient_name VARCHAR(100) NOT NULL,
  recipient VARCHAR(30) NOT NULL,
  notification_type VARCHAR(30) NOT NULL,
  message TEXT NOT NULL,
  status VARCHAR(30) NOT NULL,
  sent_at DATETIME NOT NULL,
  INDEX idx_sms_log_queue (queue_id),
  INDEX idx_sms_log_sent_at (sent_at)
);
