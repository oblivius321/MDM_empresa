-- 🚜 MIGRATION: 004_add_metadata_json_to_devices.sql
-- Adiciona a coluna metadata_json para suportar campos extras dinâmicos do Android
-- sem quebrar a estrutura rígida do banco de dados.

ALTER TABLE devices ADD COLUMN IF NOT EXISTS metadata_json JSONB;

COMMENT ON COLUMN devices.metadata_json IS 'Armazena dados extras enviados pelo dispositivo durante o enroll que não possuem colunas dedicadas.';
