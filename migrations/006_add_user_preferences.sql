-- MIGRATION: 006_add_user_preferences.sql
-- Persists notification toggles for each dashboard user.

ALTER TABLE users
ADD COLUMN IF NOT EXISTS preferences JSONB NOT NULL DEFAULT '{
  "offline_alerts": true,
  "compliance_failures": true,
  "new_devices": true,
  "system_updates": true
}'::jsonb;

UPDATE users
SET preferences = '{
  "offline_alerts": true,
  "compliance_failures": true,
  "new_devices": true,
  "system_updates": true
}'::jsonb
WHERE preferences IS NULL;

COMMENT ON COLUMN users.preferences IS 'Dashboard notification preferences used by alert delivery jobs.';
