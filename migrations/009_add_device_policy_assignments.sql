-- Direct device-to-policy assignments for enterprise policies v2.

CREATE TABLE IF NOT EXISTS device_policy_assignments (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR NOT NULL REFERENCES devices(device_id),
    policy_id INTEGER NOT NULL REFERENCES policies_v2(id),
    issued_by VARCHAR NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_device_policy_assignments_device_policy UNIQUE (device_id, policy_id)
);

CREATE INDEX IF NOT EXISTS ix_device_policy_assignments_device_id
ON device_policy_assignments (device_id);

CREATE INDEX IF NOT EXISTS ix_device_policy_assignments_policy_id
ON device_policy_assignments (policy_id);
