-- MIGRATION: 005_enterprise_hardening_sync.sql
-- Sincroniza o schema PostgreSQL com os modelos SQLAlchemy usados pela camada
-- Enterprise Policy, evitando falhas em consultas de devices/policies.

ALTER TABLE devices
ADD COLUMN IF NOT EXISTS policy_outdated BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE policies_v2
ADD COLUMN IF NOT EXISTS description TEXT;

ALTER TABLE policies_v2
ADD COLUMN IF NOT EXISTS tags JSON NOT NULL DEFAULT '[]'::json;

CREATE INDEX IF NOT EXISTS ix_devices_policy_outdated
ON devices (policy_outdated);

CREATE INDEX IF NOT EXISTS ix_policies_v2_scope
ON policies_v2 (scope);

-- O banco existente pode ter sido criado por Base.metadata.create_all, que nomeia
-- o enum como auditactionenum, ou por migrations antigas, que usavam audit_action_enum.
DO $$
DECLARE
    enum_type regtype;
    enum_value text;
BEGIN
    FOR enum_type IN
        SELECT oid::regtype
        FROM pg_type
        WHERE typname IN ('auditactionenum', 'audit_action_enum')
    LOOP
        FOREACH enum_value IN ARRAY ARRAY[
            'ROLE_DELETE',
            'ENROLLMENT_COMPLETE',
            'COMMAND_CREATE',
            'COMMAND_UPDATE',
            'COMPLIANCE_CHECK'
        ]
        LOOP
            EXECUTE format(
                'ALTER TYPE %s ADD VALUE IF NOT EXISTS %L',
                enum_type,
                enum_value
            );
        END LOOP;
    END LOOP;
END $$;
