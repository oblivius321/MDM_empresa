INSERT INTO command_queue (device_id, command, status, payload, created_at, dedupe_key, retry_count, max_retries, attempts) 
VALUES ('df610686edd54928', 'INSTALL_APK', 'PENDING', '{"url": "http://192.168.25.227:8000/static/elion-mdm.apk"}', NOW(), 'manual_update_v1', 0, 3, 0);
