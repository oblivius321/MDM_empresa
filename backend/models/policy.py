from sqlalchemy import String, Integer, JSON, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from backend.core.database import Base

if TYPE_CHECKING:
    from backend.models.device import Device


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY — Template de configuração (catálogo enterprise)
# ═══════════════════════════════════════════════════════════════════════════════

class Policy(Base):
    """
    Template de policy enterprise com config JSON flexível.

    Substituiu o modelo antigo de colunas booleanas por um JSON extensível,
    permitindo adicionar novos tipos de restrição sem migrations.

    Scope define a hierarquia de merge:
      global < group < device  (device sobrescreve global)

    Priority define a ordem de merge dentro do mesmo scope:
      maior priority → sobrescreve conflitos da menor.

    Version é incrementado em toda edição para invalidar caches
    e impedir aplicação fantasma de configuração legada.
    """
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, default="Default Policy")

    # ─── Config JSON Flexível ─────────────────────────────────────────────────
    # Exemplo:
    # {
    #   "kiosk_mode": "com.elion.app",
    #   "restrictions": {"camera_disabled": true, "factory_reset_disabled": true},
    #   "allowed_apps": ["com.android.chrome"],
    #   "blocked_apps": ["com.facebook.katana"],
    #   "password_requirements": {"required": true, "min_length": 6}
    # }
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    # ─── Merge & Hierarquia ───────────────────────────────────────────────────
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Maior = sobrescreve
    scope: Mapped[str] = mapped_column(String, default="global")  # global | group | device
    version: Mapped[int] = mapped_column(Integer, default=1)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ─── Compatibilidade legada (campos antigos) ─────────────────────────────
    # Mantidos para não quebrar frontend existente durante transição.
    device_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("devices.device_id"), nullable=True
    )
    type: Mapped[str] = mapped_column(String, default="security")
    status: Mapped[str] = mapped_column(String, default="active")
    camera_disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    install_unknown_sources: Mapped[bool] = mapped_column(Boolean, default=False)
    factory_reset_disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    kiosk_mode: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    policy_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=True)

    # ─── Relationships ────────────────────────────────────────────────────────
    device: Mapped["Device"] = relationship(back_populates="policies")
    device_policies: Mapped[List["DevicePolicy"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_policy_scope_priority', 'scope', 'priority'),
        Index('idx_policy_active', 'is_active'),
    )

    def __repr__(self):
        return f"<Policy(id={self.id}, name='{self.name}', v={self.version}, scope={self.scope})>"


# ═══════════════════════════════════════════════════════════════════════════════
# DEVICE_POLICY — Vínculo N:M (device ↔ policy)
# ═══════════════════════════════════════════════════════════════════════════════

class DevicePolicy(Base):
    """
    Vínculo N:M entre Device e Policy.

    Um device pode ter múltiplas policies atribuídas.
    Uma policy pode ser atribuída a múltiplos devices.
    issued_by registra qual admin fez a atribuição (auditoria).
    """
    __tablename__ = "device_policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[str] = mapped_column(
        String, ForeignKey("devices.device_id"), index=True
    )
    policy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("policies.id"), index=True
    )
    issued_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    policy: Mapped["Policy"] = relationship(back_populates="device_policies")

    __table_args__ = (
        Index('idx_dp_device_policy', 'device_id', 'policy_id', unique=True),
    )

    def __repr__(self):
        return f"<DevicePolicy(device={self.device_id}, policy={self.policy_id})>"


# ═══════════════════════════════════════════════════════════════════════════════
# POLICY_STATE — Telemetria de compliance por device
# ═══════════════════════════════════════════════════════════════════════════════

class PolicyState(Base):
    """
    Estado de compliance de um device em relação às policies atribuídas.

    Armazena o último estado reportado pelo device, o hash canônico para
    comparação O(1), e tracking granular de subcomandos que falharam.

    Status possíveis:
      compliant        → device matches desired state
      non_compliant    → drift detectado, aguardando enforcement
      enforcing        → comandos de correção na fila
      enforcing_partial → alguns subcomandos falharam
      failed_loop      → falha repetida, enforcement pausado (requer intervenção)
    """
    __tablename__ = "policy_state"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[str] = mapped_column(
        String, ForeignKey("devices.device_id"), unique=True, index=True
    )

    # ─── Estado reportado pelo device ─────────────────────────────────────────
    last_reported_state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=True)
    state_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # ─── Compliance ───────────────────────────────────────────────────────────
    last_compliance_status: Mapped[str] = mapped_column(String, default="unknown")
    # compliant | non_compliant | enforcing | enforcing_partial | failed_loop

    # ─── Tracking de enforcement ──────────────────────────────────────────────
    last_enforced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    enforcement_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_subcommands: Mapped[dict] = mapped_column(JSON, default=list, nullable=True)

    # ─── Cache do effective hash (evita recalcular merge) ─────────────────────
    effective_policy_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # ─── Drift/Anti-loop ──────────────────────────────────────────────────────
    drift_score: Mapped[int] = mapped_column(Integer, default=0)
    last_failed_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return (
            f"<PolicyState(device={self.device_id}, "
            f"status={self.last_compliance_status})>"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# COMMAND QUEUE — (Mantido intacto da Fase 2)
# ═══════════════════════════════════════════════════════════════════════════════

class CommandQueue(Base):
    """
    Fila de comandos para dispositivos com suporte a acknowledgment.

    Estados: pending → sent → acked → completed | failed
    Sub-estados de falha (para diagnóstico):
      failed_no_ack    → device não confirmou recepção (sent_timeout)
      failed_no_result → device confirmou mas não executou (acked_timeout)

    Idempotência (Ajuste 1):
      dedupe_key = hash(device_id + action + minute_bucket)
      Impede comandos duplicados no mesmo minuto (ex: double-click no frontend).
    """
    __tablename__ = "command_queue"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[str] = mapped_column(String, ForeignKey("devices.device_id"))
    command: Mapped[str] = mapped_column(String)  # "lock_device", etc.
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    # pending | sent | acked | completed | failed | failed_no_ack | failed_no_result

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # ─── Timestamps de ciclo de vida ──────────────────────────────────────────
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # ─── Retry e Telemetria ───────────────────────────────────────────────────
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    # ─── Diagnóstico de Falha ─────────────────────────────────────────────────
    # Taxonomia: no_ack | no_result | max_retries | device_error | transport_error | policy_violation
    error_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # ─── Idempotência Backend ─────────────────────────────────────────────────
    dedupe_key: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

    # ─── Auditoria ────────────────────────────────────────────────────────────
    issued_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # ─── Índices ──────────────────────────────────────────────────────────────
    __table_args__ = (
        Index('idx_cmd_device_status_created', 'device_id', 'status', 'created_at'),
        Index('idx_cmd_status_created', 'status', 'created_at'),
        Index(
            'idx_uniq_device_dedupe',
            'device_id',
            'dedupe_key',
            unique=True,
            postgresql_where="dedupe_key IS NOT NULL AND status IN ('pending', 'sent', 'acked')",
        ),
    )

    def __repr__(self):
        return (
            f"<CommandQueue(id={self.id}, device_id={self.device_id}, "
            f"command={self.command}, status={self.status})>"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# LOG — (Mantido intacto)
# ═══════════════════════════════════════════════════════════════════════════════

class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    type: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String, default="info")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)