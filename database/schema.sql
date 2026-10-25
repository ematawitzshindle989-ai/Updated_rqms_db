-- RQMS Database Schema — St. Paul Hospital
-- Run in phpMyAdmin or: mysql -u root -p < database/schema.sql

CREATE DATABASE IF NOT EXISTS rqms_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE rqms_db;

CREATE TABLE IF NOT EXISTS users (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  password VARCHAR(255) NOT NULL,
  full_name VARCHAR(100) NOT NULL,
  role VARCHAR(20) NOT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS queue_patients (
  queue_id INT AUTO_INCREMENT PRIMARY KEY,
  queue_number VARCHAR(20) NOT NULL,
  patient_name VARCHAR(100) NOT NULL,
  patient_phone VARCHAR(30) NULL,
  patient_priority VARCHAR(20) DEFAULT 'Regular',
  sms_enabled TINYINT(1) DEFAULT 0,
  reminder_sent TINYINT(1) DEFAULT 0,
  reminder_status VARCHAR(20) DEFAULT 'Not Sent',
  reminder_sent_at DATETIME NULL,
  service_type VARCHAR(50) NOT NULL,
  assigned_room VARCHAR(50) NOT NULL,
  status VARCHAR(20) NOT NULL,
  registered_at DATETIME NOT NULL,
  called_at DATETIME NULL,
  completed_at DATETIME NULL,
  tracking_code VARCHAR(20) NOT NULL,
  result_status VARCHAR(30) DEFAULT '—',
  result_ready_at DATETIME NULL,
  result_released_at DATETIME NULL,
  result_notify_sent TINYINT(1) DEFAULT 0,
  turn_notification_status VARCHAR(20) DEFAULT 'Not Sent',
  turn_notification_sent_at DATETIME NULL
);

CREATE TABLE IF NOT EXISTS room_catalog (
  room_id INT AUTO_INCREMENT PRIMARY KEY,
  room_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS service_catalog (
  service_id INT AUTO_INCREMENT PRIMARY KEY,
  service_name VARCHAR(50) NOT NULL UNIQUE
);

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

-- Seed staff accounts (password: 1234)
INSERT IGNORE INTO users (user_id, username, password, full_name, role) VALUES
(1, 'admin', '1234', 'Maria Santos', 'Admin'),
(2, 'staff', '1234', 'Juan Dela Cruz', 'Staff');

INSERT IGNORE INTO room_catalog (room_name) VALUES
('Room 1'),
('Room 2'),
('Room 3'),
('Room 4');

INSERT IGNORE INTO service_catalog (service_name) VALUES
('X-Ray'),
('Ultrasound'),
('CT Scan'),
('MRI'),
('Mammography'),
('Fluoroscopy');

-- Sample queue data
INSERT IGNORE INTO queue_patients
  (queue_id, queue_number, patient_name, service_type, assigned_room, status,
   registered_at, called_at, completed_at, tracking_code, result_status, result_ready_at, result_notify_sent)
VALUES
(1, 'R-101', 'Ana Reyes', 'X-Ray', 'Room 1', 'Waiting', DATE_SUB(NOW(), INTERVAL 45 MINUTE), NULL, NULL, 'TRK-101', '—', NULL, 0),
(2, 'R-102', 'Pedro Gomez', 'Ultrasound', 'Room 2', 'Waiting', DATE_SUB(NOW(), INTERVAL 30 MINUTE), NULL, NULL, 'TRK-102', '—', NULL, 0),
(3, 'R-103', 'Liza Tan', 'CT Scan', 'Room 3', 'Called', DATE_SUB(NOW(), INTERVAL 20 MINUTE), DATE_SUB(NOW(), INTERVAL 5 MINUTE), NULL, 'TRK-103', '—', NULL, 0),
(4, 'R-104', 'Rosa Lim', 'MRI', 'Room 4', 'Completed', DATE_SUB(NOW(), INTERVAL 2 HOUR), DATE_SUB(NOW(), INTERVAL 3 HOUR), DATE_SUB(NOW(), INTERVAL 2 HOUR), 'TRK-104', 'Ready for Release', DATE_SUB(NOW(), INTERVAL 30 MINUTE), 1);

-- Additional sample: exam done, result still processing
INSERT IGNORE INTO queue_patients
  (queue_id, queue_number, patient_name, service_type, assigned_room, status,
   registered_at, called_at, completed_at, tracking_code, result_status)
VALUES
(5, 'R-105', 'Carlos Mendoza', 'X-Ray', 'Room 1', 'Completed',
 DATE_SUB(NOW(), INTERVAL 90 MINUTE), DATE_SUB(NOW(), INTERVAL 80 MINUTE),
 DATE_SUB(NOW(), INTERVAL 75 MINUTE), 'TRK-105', 'Processing');
