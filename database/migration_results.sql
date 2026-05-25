-- Run once on existing rqms_db (phpMyAdmin)
USE rqms_db;

-- Columns are auto-added when you start Flask (ensure_result_columns).
-- Or run these manually if needed:

-- ALTER TABLE queue_patients ADD COLUMN result_status VARCHAR(30) DEFAULT '—';
-- ALTER TABLE queue_patients ADD COLUMN result_ready_at DATETIME NULL;
-- ALTER TABLE queue_patients ADD COLUMN result_released_at DATETIME NULL;
-- ALTER TABLE queue_patients ADD COLUMN result_notify_sent TINYINT(1) DEFAULT 0;

UPDATE queue_patients
SET status = 'Completed',
    completed_at = COALESCE(completed_at, DATE_SUB(NOW(), INTERVAL 2 HOUR)),
    result_status = 'Ready for Release',
    result_ready_at = DATE_SUB(NOW(), INTERVAL 30 MINUTE),
    result_notify_sent = 1
WHERE queue_number = 'R-104';
