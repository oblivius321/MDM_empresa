-- MIGRAÇÃO: command_queue
-- dedupe_key (idempotência)
ALTER TABLE command_queue
ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR;

-- status lifecycle
ALTER TABLE command_queue
ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'PENDING';

-- timestamps
ALTER TABLE command_queue
ADD COLUMN IF NOT EXISTS sent_at TIMESTAMP;
ALTER TABLE command_queue
ADD COLUMN IF NOT EXISTS acked_at TIMESTAMP;
ALTER TABLE command_queue
ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP;

-- retry system
ALTER TABLE command_queue
ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
ALTER TABLE command_queue
ADD COLUMN IF NOT EXISTS max_retries INTEGER DEFAULT 3;
ALTER TABLE command_queue
ADD COLUMN IF NOT EXISTS attempts INTEGER DEFAULT 0;

-- error tracking
ALTER TABLE command_queue
ADD COLUMN IF NOT EXISTS error_code VARCHAR;
ALTER TABLE command_queue
ADD COLUMN IF NOT EXISTS error_message TEXT;

-- índice único para dedupe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE indexname = 'idx_command_dedupe'
    ) THEN
        CREATE UNIQUE INDEX idx_command_dedupe ON command_queue (dedupe_key);
    END IF;
END$$;

-- MIGRAÇÃO: audit_logs
ALTER TABLE audit_logs
ADD COLUMN IF NOT EXISTS event_type VARCHAR;

ALTER TABLE audit_logs
ADD COLUMN IF NOT EXISTS severity VARCHAR;

ALTER TABLE audit_logs
ADD COLUMN IF NOT EXISTS actor_type VARCHAR;

ALTER TABLE audit_logs
ADD COLUMN IF NOT EXISTS actor_id VARCHAR;

ALTER TABLE audit_logs
ADD COLUMN IF NOT EXISTS device_id UUID;

ALTER TABLE audit_logs
ADD COLUMN IF NOT EXISTS request_id VARCHAR;

-- índices importantes
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs (event_type);
CREATE INDEX IF NOT EXISTS idx_audit_device_id ON audit_logs (device_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_logs (created_at);

-- Cleanup opcional
DROP TABLE IF EXISTS device_commands;
