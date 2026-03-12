-- Migração: Adicionar suporte a password reset seguro com JTI
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_jti VARCHAR DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_jti_expires TIMESTAMP DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_answer_verified_at TIMESTAMP DEFAULT NULL;

-- Criar índice para performance
CREATE INDEX IF NOT EXISTS idx_users_password_reset_jti ON users(password_reset_jti) WHERE password_reset_jti IS NOT NULL;

-- Verificar se foi criado
\d users
