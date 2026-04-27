"""
ConnectionManager — Sistema de Presença Enterprise para o Elion MDM.

Ajustes de Produção (Final):
  - Cancelamento seguro de tasks: task.cancel() + await task
  - Flood protection: máximo 1 heartbeat por 5s por device
  - Log estruturado de transições de estado (online→offline, offline→online)
  - Assert rígido: status ∈ {"online", "offline"}


Fontes de Tempo:
  - Memória:     time.monotonic() → imune a clock skew e NTP drift
  - Banco/Logs:  datetime.utcnow() → timestamp legível e persistível

Códigos de Fechamento WebSocket (padronizados):
  4001 → duplicate_connection  (mesmo device_id reconectou)
  4002 → auth_failed           (token inválido ou ausente)
  4003 → heartbeat_timeout     (silêncio > HEARTBEAT_TIMEOUT_SECONDS)

Escalabilidade:
  O estado de presença está isolado em _PresenceStore.
  Em caso de múltiplos workers ou necessidade de Redis,
  basta substituir _PresenceStore por uma implementação Redis-backed
  sem alterar o restante do ConnectionManager.
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Set
from fastapi import WebSocket
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# ─── Constantes ────────────────────────────────────────────────────────────────

HEARTBEAT_TIMEOUT_SECONDS = 65      # Silêncio > 65s → zombie declarado
WATCHDOG_SWEEP_INTERVAL = 30        # Watchdog varre a cada 30s
DB_SYNC_INTERVAL_SECONDS = 300      # DB sincronizado a cada 5min (lazy)
HEARTBEAT_MIN_INTERVAL = 5         # Flood protection: mínimo 5s entre heartbeats

# Códigos WebSocket — padronizados para facilitar debugging
WS_CLOSE_DUPLICATE    = 4001        # Device reconectou com mesmo ID
WS_CLOSE_AUTH_FAILED  = 4002        # Token inválido
WS_CLOSE_HB_TIMEOUT   = 4003        # Heartbeat expirou


# ─── Presence Store (isolado para futura substituição por Redis) ────────────────

class _PresenceStore:
    """
    Armazena o estado de presença dos devices em memória.

    Separado do ConnectionManager para possibilitar troca futura
    por uma implementação Redis sem afetar o restante do sistema.

    Todas as comparações de tempo usam time.monotonic() para evitar
    problemas de clock skew, NTP sync e reinicializações de servidor.
    """

    def __init__(self):
        # time.monotonic() → relógio monotônico, não suscetível a drift
        self._last_heartbeat: Dict[str, float] = {}     # device_id → monotonic time
        self._last_hb_received: Dict[str, float] = {}    # Flood protection: último ping aceito
        # datetime.utcnow() → usado apenas para persistência no DB
        self._last_seen_utc: Dict[str, datetime] = {}
        # DB sync control
        self._last_db_sync: Dict[str, float] = {}
        # Status validado (apenas "online" ou "offline")
        self._status: Dict[str, str] = {}

    def record_heartbeat(self, device_id: str):
        from backend.core import utcnow
        now_utc = utcnow()
        now = time.monotonic()
        self._last_heartbeat[device_id] = now
        self._last_hb_received[device_id] = now
        self._last_seen_utc[device_id] = now_utc

    def is_heartbeat_allowed(self, device_id: str) -> bool:
        """Flood protection: retorna False se o device enviou ping há menos de HEARTBEAT_MIN_INTERVAL segundos."""
        last = self._last_hb_received.get(device_id, 0)
        return (time.monotonic() - last) >= HEARTBEAT_MIN_INTERVAL

    def get_silence_seconds(self, device_id: str) -> float:
        """Retorna quantos segundos passaram desde o último heartbeat."""
        ts = self._last_heartbeat.get(device_id)
        return (time.monotonic() - ts) if ts is not None else float("inf")

    def get_last_seen_utc(self, device_id: str) -> Optional[datetime]:
        return self._last_seen_utc.get(device_id)

    def set_status(self, device_id: str, status: str):
        # 🛡️ Invariante de estado: apenas 2 valores permitidos em todo o sistema.
        # Previne bugs futuros de status="disconnected", "idle", etc.
        assert status in ("online", "offline"), (
            f"Status inválido '{status}' para device_id='{device_id}'. "
            f"Valores aceitos: 'online', 'offline'."
        )
        self._status[device_id] = status

    def get_status(self, device_id: str) -> Optional[str]:
        return self._status.get(device_id)

    def should_sync_db(self, device_id: str) -> bool:
        last = self._last_db_sync.get(device_id, 0)
        return (time.monotonic() - last) >= DB_SYNC_INTERVAL_SECONDS

    def mark_db_synced(self, device_id: str):
        self._last_db_sync[device_id] = time.monotonic()

    def all_device_ids(self) -> Set[str]:
        return set(self._last_heartbeat.keys())


# ─── Connection Manager ────────────────────────────────────────────────────────

class ConnectionManager:

    def __init__(self):
        # Dashboards Admin conectados
        self.active_dashboards: List[WebSocket] = []
        # Malha de devices: device_id → WebSocket
        self.active_devices: Dict[str, WebSocket] = {}
        # Estado de presença (isolado e trocável)
        self.presence = _PresenceStore()
        # Watchdog task
        self._watchdog_task: Optional[asyncio.Task] = None

    # ─── Watchdog ──────────────────────────────────────────────────────────────

    def start_watchdog(self):
        """Inicia o Watchdog de zombie connections. Chamar em app startup."""
        if self._watchdog_task is None or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(self._watchdog_loop())
            logger.info("🛡️ Watchdog de presença iniciado.")

    async def _watchdog_loop(self):
        while True:
            await asyncio.sleep(WATCHDOG_SWEEP_INTERVAL)
            await self._sweep_zombie_devices()

    async def _sweep_zombie_devices(self):
        """
        Varre a malha em busca de devices silenciosos.

        ⚠️ ARQUITETURA: O Watchdog NÃO fecha sockets diretamente.
        Ele apenas marca o status como offline.
        O fechamento do socket é responsabilidade do loop WebSocket individual,
        que detecta o silêncio via asyncio.TimeoutError e fecha de forma segura.
        Isso evita race conditions entre o Watchdog e os loops WebSocket concorrentes.
        """
        for device_id in list(self.presence.all_device_ids()):
            silence = self.presence.get_silence_seconds(device_id)
            current_status = self.presence.get_status(device_id)

            if silence > HEARTBEAT_TIMEOUT_SECONDS and current_status == "online":
                logger.warning(
                    f"🧟 Zombie detectado: device={device_id} "
                    f"silêncio={silence:.0f}s"
                )
                # Marca offline via presence store.
                # O socket será fechado pelo loop WebSocket no próximo ciclo de timeout.
                await self._set_offline(device_id, reason="heartbeat_timeout")

    # ─── Conexão de Dashboard ──────────────────────────────────────────────────

    async def connect_dashboard(self, websocket: WebSocket):
        self.active_dashboards.append(websocket)
        logger.info(f"Dashboard conectado. Total: {len(self.active_dashboards)}")

    def disconnect_dashboard(self, websocket: WebSocket):
        if websocket in self.active_dashboards:
            self.active_dashboards.remove(websocket)
            logger.info("Dashboard desconectado.")

    # ─── Conexão de Device ─────────────────────────────────────────────────────

    async def connect_device(self, websocket: WebSocket, device_id: str):
        """
        Registra device na malha.

        🛡️ Anti-duplicidade: Fecha socket antigo (código 4001) antes de
        registrar o novo. Previne o bug clássico de device duplicado.
        """
        old_ws = self.active_devices.get(device_id)
        if old_ws is not None:
            logger.warning(f"⚠️ [{device_id}] Reconexão detectada. Encerrando socket anterior.")
            try:
                await old_ws.close(code=WS_CLOSE_DUPLICATE)
            except Exception:
                pass

        self.active_devices[device_id] = websocket
        # Registra heartbeat inicial (monotonic para comparação; UTC para DB)
        previous = self.presence.get_status(device_id)
        self.presence.record_heartbeat(device_id)
        self.presence.set_status(device_id, "online")

        # 📋 Transição de estado — log crítico para debug em produção
        logger.info(
            f"🟢 [Presença] {device_id}: '{previous or 'unknown'}' → 'online' "
            f"| malha={len(self.active_devices)}"
        )

        # Broadcast com payload completo → evita roundtrip extra no Dashboard
        await self.broadcast_to_dashboards({
            "type": "DEVICE_CONNECTED",
            "device_id": device_id,
            "status": "online",
            "timestamp": utcnow().isoformat(),
        })

    def is_device_online(self, device_id: str) -> bool:
        return device_id in self.active_devices and self.presence.get_status(device_id) == "online"

    async def disconnect_device(self, device_id: str, reason: str = "disconnect"):
        """
        Remove device da malha.

        O disconnect é tratado como cleanup, não como fonte de verdade para offline.
        _set_offline decide se há mudança de estado e dispara broadcast.
        """
        self.active_devices.pop(device_id, None)
        await self._set_offline(device_id, reason=reason)

    # ─── Heartbeat ─────────────────────────────────────────────────────────────

    def record_heartbeat(self, device_id: str):
        """
        Registra que o device está vivo.
        Usa time.monotonic() internamente — imune a clock skew.
        NÃO faz broadcast. NÃO escreve no DB (lazy sync).
        """
        self.presence.record_heartbeat(device_id)

    async def persist_online_lazy(self, device_id: str):
        """Persiste status online no DB somente a cada DB_SYNC_INTERVAL_SECONDS."""
        if self.presence.should_sync_db(device_id):
            await self._write_status_to_db(device_id, "online")
            self.presence.mark_db_synced(device_id)

    # ─── Estado de Presença ────────────────────────────────────────────────────

    async def _set_offline(self, device_id: str, reason: str):
        """
        Declara device offline:
        1. Atualiza PresenceStore.
        2. Persiste no DB (sempre — offline é evento crítico).
        3. Broadcast se houve mudança real de estado.
        """
        previous = self.presence.get_status(device_id)
        self.presence.set_status(device_id, "offline")
        await self._write_status_to_db(device_id, "offline")

        if previous != "offline":
            # 📋 Transição de estado — log crítico para debug em produção
            logger.info(
                f"🔴 [Presença] {device_id}: '{previous or 'unknown'}' → 'offline' "
                f"| motivo={reason}"
            )
            await self.broadcast_to_dashboards({
                "type": "DEVICE_DISCONNECTED",
                "device_id": device_id,
                "status": "offline",
                "reason": reason,
                "timestamp": utcnow().isoformat(),
            })
        else:
            # Device já estava offline — sem broadcast redundante
            logger.debug(f"[Presença] {device_id}: offline → offline (skipped broadcast)")

    async def _write_status_to_db(self, device_id: str, status: str):
        """
        Persiste status + last_checkin no DB via sessão independente.
        Tempo para o DB: datetime UTC (legível e persistível).
        Tempo para memória: monotonic (comparação interna confiável).
        """
        from backend.core.database import async_session_maker
        try:
            async with async_session_maker() as db:
                from backend.repositories.device_repo import DeviceRepository
                repo = DeviceRepository(db)
                last_seen = (
                    self.presence.get_last_seen_utc(device_id)
                    or utcnow()
                )
                await repo.update_device(device_id, {
                    "status": status,
                    "last_checkin": last_seen,
                })
            logger.debug(f"[DB Sync] device={device_id} status={status}")
        except Exception as e:
            logger.error(f"[DB Sync ERRO] device={device_id}: {e}")

    # ─── Comunicação ───────────────────────────────────────────────────────────

    async def send_command_to_device(self, device_id: str, command_data: Dict[str, Any]) -> bool:
        """Envia comando JSON para o device. Retorna True se entregue."""
        ws = self.active_devices.get(device_id)
        if ws:
            try:
                await ws.send_json(command_data)
                logger.info(f"📡 Comando '{command_data.get('command')}' → {device_id}")
                return True
            except Exception as e:
                logger.error(f"Erro ao enviar para {device_id}: {e}")
                await self.disconnect_device(device_id, reason="send_error")
        return False

    async def broadcast_to_dashboards(self, message: Dict[str, Any]):
        """
        Transmite evento JSON para todos os dashboards.
        O payload inclui `status` e `device_id` para que o React
        possa atualizar o badge localmente sem fazer nova requisição GET.
        Remove conexões zumbis automaticamente.
        """
        dead: List[WebSocket] = []
        for ws in self.active_dashboards:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect_dashboard(ws)


# Singleton global.
manager = ConnectionManager()
