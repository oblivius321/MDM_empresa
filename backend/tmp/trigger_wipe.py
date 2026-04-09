import asyncio
import os
import sys
import traceback

# Ajusta o path para o root (/app)
sys.path.append("/app")

# IMPORTANTE: Importar os modelos para registrar no SQLAlchemy Metadata
try:
    import backend.models.user
    import backend.models.device
    import backend.models.policy
    import backend.models.telemetry
    import backend.models.audit_log
except Exception:
    print("⚠️ Aviso: Erro ao importar modelos (pode ser esperado se já carregados)")

from backend.core.database import async_session_maker
from backend.repositories.device_repo import DeviceRepository
from backend.services.mdm_service import MDMService

async def trigger_wipe(device_id: str):
    async with async_session_maker() as db:
        repo = DeviceRepository(db)
        service = MDMService(repo)
        
        actor_id = "admin@elion.com.br"
        
        print(f"🚀 Enviando comando WIPE para o dispositivo: {device_id}...")
        
        try:
            # Enfileira o comando na nova arquitetura unificada
            cmd = await service.enqueue_command(
                device_id=device_id,
                command_type="WIPE",
                actor_id=actor_id,
                payload={"include_external_storage": "false"}
            )
            print(f"✅ Comando enfileirado com sucesso!")
            print(f"🆔 ID do Comando: {cmd.id}")
            print(f"📡 Status: PENDING (Aguardando conexão do dispositivo)")
        except Exception as e:
            print(f"❌ Erro ao enviar comando: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python trigger_wipe.py <device_id>")
    else:
        asyncio.run(trigger_wipe(sys.argv[1]))
