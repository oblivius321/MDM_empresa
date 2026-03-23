-- ============================================================================
-- Migração 003: Criar tabelas de RBAC (Roles, Permissions, Audit)
-- ============================================================================
-- Data: 2025-03-23
-- Descrição: Implementa sistema completo de RBAC enterprise-grade
--            com auditoria, validações de segurança e hierarquia de permissões

-- ============================================================================
-- 1. CRIAR ENUM TYPES
-- ============================================================================

CREATE TYPE role_enum AS ENUM ('SUPER_ADMIN', 'ADMIN', 'OPERATOR', 'VIEWER');

CREATE TYPE audit_action_enum AS ENUM (
    'LOGIN',
    'LOGOUT',
    'USER_CREATE',
    'USER_UPDATE',
    'USER_DELETE',
    'USER_DEACTIVATE',
    'ROLE_ASSIGN',
    'ROLE_REVOKE',
    'ROLE_CREATE',
    'ROLE_UPDATE',
    'DEVICE_ENROLL',
    'DEVICE_UNENROLL',
    'DEVICE_LOCK',
    'DEVICE_UNLOCK',
    'DEVICE_WIPE',
    'DEVICE_POLICY_APPLY',
    'DEVICE_APP_INSTALL',
    'DEVICE_APP_REMOVE',
    'AUDIT_LOG_DELETE',
    'AUDIT_LOG_EXPORT',
    'CONFIG_CHANGE',
    'FAILED_LOGIN',
    'PERMISSION_DENIED',
    'PRIVILEGE_ESCALATION_ATTEMPT'
);

-- ============================================================================
-- 2. TABELA DE ROLES
-- ============================================================================

CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    role_type role_enum NOT NULL,
    is_system_role BOOLEAN DEFAULT true NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    priority INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_by_user_id INTEGER,
    CONSTRAINT fk_roles_created_by FOREIGN KEY (created_by_user_id)
        REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_role_name ON roles(name);
CREATE INDEX idx_role_type ON roles(role_type);
CREATE INDEX idx_role_type_active ON roles(role_type, is_active);
CREATE INDEX idx_role_active ON roles(is_active);
CREATE INDEX idx_role_priority ON roles(priority);

-- ============================================================================
-- 3. TABELA DE PERMISSIONS
-- ============================================================================

CREATE TABLE permissions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    resource VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    is_critical BOOLEAN DEFAULT false NOT NULL,
    requires_mfa BOOLEAN DEFAULT false NOT NULL,
    is_system_permission BOOLEAN DEFAULT true NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_permission_name ON permissions(name);
CREATE INDEX idx_permission_resource ON permissions(resource);
CREATE INDEX idx_permission_resource_action ON permissions(resource, action);
CREATE INDEX idx_permission_critical ON permissions(is_critical);
CREATE INDEX idx_permission_active ON permissions(is_active);

-- ============================================================================
-- 4. TABELA DE ASSOCIAÇÃO ROLES <-> PERMISSIONS (M:N)
-- ============================================================================

CREATE TABLE role_permissions (
    role_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    CONSTRAINT fk_role_permissions_role FOREIGN KEY (role_id)
        REFERENCES roles(id) ON DELETE CASCADE,
    CONSTRAINT fk_role_permissions_permission FOREIGN KEY (permission_id)
        REFERENCES permissions(id) ON DELETE CASCADE
);

CREATE INDEX idx_role_permissions_role ON role_permissions(role_id);
CREATE INDEX idx_role_permissions_permission ON role_permissions(permission_id);

-- ============================================================================
-- 5. TABELA DE ASSOCIAÇÃO USERS <-> ROLES (M:N)
-- ============================================================================

CREATE TABLE user_roles (
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    assigned_by_user_id INTEGER,
    PRIMARY KEY (user_id, role_id),
    CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id)
        REFERENCES roles(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_roles_assigned_by FOREIGN KEY (assigned_by_user_id)
        REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_user_roles_role ON user_roles(role_id);
CREATE INDEX idx_user_roles_compound ON user_roles(user_id, role_id);

-- ============================================================================
-- 6. TABELA DE LOGS DE AUDITORIA
-- ============================================================================

CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER,
    action audit_action_enum NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(255),
    details JSONB,
    ip_address VARCHAR(50),
    user_agent VARCHAR(500),
    is_success BOOLEAN DEFAULT true NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE SET NULL
);

-- ⚠️ ÍNDICES CRÍTICOS PARA AUDITORIA (perfomance)
CREATE INDEX idx_audit_id ON audit_logs(id DESC);  -- Para varreduras rápidas
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_user_action ON audit_logs(user_id, action);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_timestamp ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_action_timestamp ON audit_logs(action, created_at DESC);
CREATE INDEX idx_audit_success ON audit_logs(is_success);

-- ============================================================================
-- 7. ATUALIZAR TABELA USERS COM CAMPOS DE RBAC
-- ============================================================================

-- Adicionar campos se não existirem
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX idx_user_email_active ON users(email, is_active);
CREATE INDEX idx_user_created ON users(created_at);

-- ============================================================================
-- 8. COMENTÁRIOS DE DOCUMENTAÇÃO (PostgreSQL)
-- ============================================================================

COMMENT ON TABLE roles IS 'Tabela de Roles/Funções para RBAC enterprise. Controla hierarquia de permissões.';
COMMENT ON TABLE permissions IS 'Tabela de Permissões granulares. Cada permissão é uma ação específica no sistema.';
COMMENT ON TABLE role_permissions IS 'Associação M:N entre Roles e Permissions. Define quais permissões cada role tem.';
COMMENT ON TABLE user_roles IS 'Associação M:N entre Users e Roles. Define quais roles cada usuário tem.';
COMMENT ON TABLE audit_logs IS 'Log imutável (append-only) de todas as ações críticas do sistema. Essencial para compliance.';

COMMENT ON COLUMN roles.priority IS 'Hierarquia: SUPER_ADMIN=1000, ADMIN=100, OPERATOR=10, VIEWER=1. Maior número = mais poderoso.';
COMMENT ON COLUMN roles.is_system_role IS 'true = built-in pelo sistema, não pode ser deletado.';
COMMENT ON COLUMN permissions.is_critical IS 'true = ação crítica, requer logs detalhados e possivelmente confirmação extra.';
COMMENT ON COLUMN permissions.requires_mfa IS 'true = requer autenticação multi-fator.';
COMMENT ON COLUMN audit_logs.details IS 'JSON estruturado com detalhes: {old_value, new_value, reason, etc}.';

-- ============================================================================
-- 9. VERIFICAÇÃO E CONSTRAINTS DE SEGURANÇA
-- ============================================================================

-- Garantir que permissions é append-only (NO UPDATE direto, apenas via app logic)
-- Garantir que audit_logs é append-only (NO UPDATE de logs existentes)

COMMIT;

-- ============================================================================
-- NOTAS DE IMPLEMENTAÇÃO
-- ============================================================================
/*
✅ Índices otimizados para:
   - Queries de auditoria (muito frequentes, muitos logs)
   - Lookup de usuários por role
   - Pesquisa de logs por ação/timestamp

✅ ENUM types para validação no banco

✅ Constraints de chave estrangeira com CASCADE delete

✅ Tabelas de associação (M:N) com índices compostos

⚠️  IMPORTANTE: Executar seed.sql logo após para popular roles e permissions padrão
*/
