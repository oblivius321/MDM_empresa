-- Migração: Adicionar suporte a password reset seguro com JTI
-- Data: 2026-03-12
-- Descrição: Adiciona colunas para rastrear password reset tokens com one-time use (JTI)

-- Aqui adicionamos campos para rastrear:
-- 1. password_reset_jti: JTI do token em vigência (garante one-time)
-- 2. password_reset_jti_expires: quando o JTI expira
-- 3. password_reset_answer_verified_at: quando a resposta foi verificada (para validar TTL)

ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_jti VARCHAR DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_jti_expires TIMESTAMP DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_answer_verified_at TIMESTAMP DEFAULT NULL;

-- Criar índice para performance ao buscar por JTI
CREATE INDEX IF NOT EXISTS idx_users_password_reset_jti 
    ON users(password_reset_jti) 
    WHERE password_reset_jti IS NOT NULL;

-- Verificar se as colunas foram criadas corretamente
SELECT EXISTS(
   SELECT FROM information_schema.columns 
   WHERE table_name = 'users' AND column_name = 'password_reset_jti'
) as password_reset_jti_exists,
EXISTS(
   SELECT FROM information_schema.columns 
   WHERE table_name = 'users' AND column_name = 'password_reset_jti_expires'
) as password_reset_jti_expires_exists,
EXISTS(
   SELECT FROM information_schema.columns 
   WHERE table_name = 'users' AND column_name = 'password_reset_answer_verified_at'
) as password_reset_answer_verified_at_exists;
