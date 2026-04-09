import asyncio
from backend.core.database import async_session_maker
from backend.repositories.device_repo import DeviceRepository
from backend.services.mdm_service import MDMService

async def trigger_wipe(device_id: str):
    async with async_session_maker() as db:
        repo = DeviceRepository(db)
        service = MDMService(repo)
        
        # O sistema exige um actor_id para auditoria
        actor_id = "admin@elion.com.br"
        
        print(f"🚀 Enviando comando WIPE para o dispositivo: {device_id}...")
        
        try:
            cmd = await service.enqueue_command(
                device_id=device_id,
                command_type="WIPE",
                actor_id=actor_id,
                payload={"include_external_storage": "false"}
            )
            print(f"✅ Comando enfileirado com sucesso!")
            print(f"🆔 ID do Comando: {cmd.id}")
            print(f"📡 O comando será enviado assim que o dispositivo estiver online.")
        except Exception as e:
            print(f"❌ Erro ao enviar comando: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python trigger_wipe.py <device_id>")
    else:
        asyncio.run(trigger_wipe(sys.argv[1]))
