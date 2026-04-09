INSERT INTO command_queue (device_id, command, status, payload, created_at, dedupe_key, retry_count, max_retries, attempts) 
VALUES ('df610686edd54928', 'WIPE', 'PENDING', '{"include_external_storage": "false"}', NOW(), 'manual_force_wipe_v1', 0, 3, 0);
