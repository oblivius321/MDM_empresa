CREATE TABLE IF NOT EXISTS android_management_config (
    id INTEGER PRIMARY KEY DEFAULT 1,
    project_id VARCHAR,
    service_account_email VARCHAR,
    signup_url_name VARCHAR,
    signup_url TEXT,
    enterprise_name VARCHAR,
    enterprise_display_name VARCHAR,
    policy_name VARCHAR,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_android_management_config_enterprise_name
    ON android_management_config (enterprise_name);

CREATE TABLE IF NOT EXISTS android_management_enrollment_tokens (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    value_prefix VARCHAR,
    policy_name VARCHAR,
    qr_code TEXT NOT NULL,
    additional_data JSON DEFAULT '{}'::json,
    expiration_timestamp VARCHAR,
    created_by VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_android_management_enrollment_tokens_name
    ON android_management_enrollment_tokens (name);

CREATE INDEX IF NOT EXISTS ix_android_management_enrollment_tokens_created_at
    ON android_management_enrollment_tokens (created_at);
