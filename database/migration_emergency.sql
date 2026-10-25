-- Run once on an existing rqms_db (phpMyAdmin).
USE rqms_db;

CREATE TABLE IF NOT EXISTS emergency_cases (
  emergency_id INT AUTO_INCREMENT PRIMARY KEY,
  activated_at DATETIME NOT NULL,
  deactivated_at DATETIME NULL,
  activated_by INT NULL,
  deactivated_by INT NULL,
  sms_notification_started_at DATETIME NULL,
  INDEX idx_emergency_active (deactivated_at),
  CONSTRAINT fk_emergency_activated_by
    FOREIGN KEY (activated_by) REFERENCES users(user_id),
  CONSTRAINT fk_emergency_deactivated_by
    FOREIGN KEY (deactivated_by) REFERENCES users(user_id)
);
