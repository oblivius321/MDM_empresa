-- Adds the Google Android Management device identifier without changing
-- existing local/manual device records.

ALTER TABLE devices
ADD COLUMN IF NOT EXISTS external_id VARCHAR;

CREATE UNIQUE INDEX IF NOT EXISTS ux_devices_external_id_not_null
ON devices (external_id)
WHERE external_id IS NOT NULL;

COMMENT ON COLUMN devices.external_id IS
'Google Android Management device id extracted from enterprises/{enterprise}/devices/{device}.';
