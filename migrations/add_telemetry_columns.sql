-- Migração: Adicionar colunas de telemetria em tempo real na tabela devices
ALTER TABLE devices ADD COLUMN IF NOT EXISTS battery_level INTEGER DEFAULT NULL;
ALTER TABLE devices ADD COLUMN IF NOT EXISTS free_disk_space_mb INTEGER DEFAULT NULL;
ALTER TABLE devices ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION DEFAULT NULL;
ALTER TABLE devices ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION DEFAULT NULL;

-- Criar índices para localização se necessário no futuro
CREATE INDEX IF NOT EXISTS idx_devices_coords ON devices(latitude, longitude) WHERE latitude IS NOT NULL;

-- Verificar colunas adicionadas
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'devices' 
AND column_name IN ('battery_level', 'free_disk_space_mb', 'latitude', 'longitude');
