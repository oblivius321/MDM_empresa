-- Migração: Adicionar suporte a pergunta de segurança para recuperação de senha
-- Data: 2026-03-11
-- Descrição: Adiciona colunas security_question e security_answer_hash à tabela users

ALTER TABLE users ADD COLUMN IF NOT EXISTS security_question VARCHAR;
ALTER TABLE users ADD COLUMN IF NOT EXISTS security_answer_hash VARCHAR;

-- Verificar se as colunas foram criadas
SELECT EXISTS(
   SELECT FROM information_schema.columns 
   WHERE table_name = 'users' AND column_name = 'security_question'
) as security_question_exists,
EXISTS(
   SELECT FROM information_schema.columns 
   WHERE table_name = 'users' AND column_name = 'security_answer_hash'
) as security_answer_hash_exists;
