<p align="center">
  <h1 align="center">⚡ Elion MDM — Backend</h1>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python" />
    <img src="https://img.shields.io/badge/FastAPI-0.95+-009688?style=flat-square&logo=fastapi" />
    <img src="https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=flat-square" />
    <img src="https://img.shields.io/badge/PostgreSQL-15-4169E1?style=flat-square&logo=postgresql" />
    <img src="https://img.shields.io/badge/Redis-7+-DC382D?style=flat-square&logo=redis" />
  </p>
</p>

> 🔙 [Voltar ao README Principal](../README.md) · 📱 [Android Agent](../android/README.md) · 🖥️ [Frontend](../frontend/README.md)

---

## Visão Geral

O backend é o sistema nervoso central do Elion MDM. Ele gerencia enrollment de dispositivos, computação de políticas, despacho de comandos, avaliação de compliance, atestação de hardware e comunicação em tempo real — tudo através de uma arquitetura assíncrona e não-bloqueante.

**O backend é exposto diretamente via Uvicorn na porta `8200` do host (mapeada de `8000` internamente no Docker), sem necessidade de Nginx ou proxy reverso.**

---

## Estrutura de Diretórios

```
backend/
├── main.py                     # Setup do app, middleware, inicialização dos watchdogs
├── api/
│   ├── routes.py               # API principal (devices, enrollment, atestação)
│   ├── auth.py                 # Autenticação JWT (login/registro de usuários)
│   ├── device_auth.py          # Validação de token opaco do dispositivo (SHA-256)
│   ├── websockets.py           # Gerenciador de conexões WebSocket
│   ├── websocket_routes.py     # Endpoints WS (canais device + dashboard)
│   ├── command_dispatcher.py   # Motor idempotente de despacho de comandos
│   ├── policy_routes.py        # CRUD de políticas e atribuição a devices
│   └── rbac_routes.py          # Gerenciamento de roles e permissões
├── services/
│   ├── mdm_service.py          # Lógica de negócio principal
│   ├── attestation_service.py  # Integração Play Integrity
│   ├── redis_service.py        # Cache, anti-replay, rate limiting
│   ├── policy_engine.py        # Funções puras: hash, merge, diff
│   ├── drift_detector.py       # Orquestrador de avaliação de compliance
│   └── rbac_service.py         # Controle de acesso baseado em roles
├── models/                     # Modelos ORM SQLAlchemy
├── schemas/                    # Modelos Pydantic de request/response
├── repositories/               # Camada assíncrona de acesso a dados
├── middleware/
│   └── observability.py        # Logs JSON, injeção de Correlation-ID
├── core/
│   ├── config.py               # Configuração baseada em variáveis de ambiente
│   ├── database.py             # Engine AsyncPG
│   ├── security.py             # Hash de senhas, geração de tokens
│   ├── constants.py            # Enum do ciclo de vida de comandos
│   ├── limiter.py              # Rate limiter (SlowAPI)
│   └── time.py                 # Utilitários UTC
└── utils/
    ├── logging_config.py       # Configuração de logs estruturados
    └── rbac_constants.py       # Definições de permissões/roles
```

---

## Arquitetura de Serviços

### `MDMService` — Lógica de Negócio Principal

| Método | Responsabilidade |
|---|---|
| `enroll_device()` | Enrollment atômico: valida profile → gera token → materializa política → salva telemetria inicial |
| `get_bootstrap_data()` | Retorna o SSOT completo (Single Source of Truth) para provisionamento |
| `process_checkin()` | Processa check-in de telemetria (bateria, GPS, apps, armazenamento) |
| `sync_policy()` | Handshake de comparação de hash para drift detection |
| `enqueue_command()` | Adiciona comando à fila idempotente com trilha de auditoria |
| `ack_command()` | Processa o ciclo de 4 estágios: ACK → EXECUTED → VERIFIED |
| `calculate_compliance_score()` | Motor ponderado: Kiosk(40) + Segurança(30) + Apps(20) + Integridade(10) |

### `AttestationService` — Trust de Hardware

| Método | Responsabilidade |
|---|---|
| `generate_nonce()` | Nonce HMAC-SHA256 vinculado a `device_id + tenant_id + request_id`, TTL 5min |
| `verify_device_integrity()` | Validação completa: Assinatura → Expiração(±60s) → Binding → Anti-Replay → API Google |
| `_calculate_trust_score()` | Score de confiança 0–100: STRONG(100) · DEVICE(60) · BASIC(20) · NONE(0) |

### `PolicyEngine` — Funções Puras (Zero I/O)

| Função | Responsabilidade |
|---|---|
| `to_canonical_json()` | Normalização JSON determinística (chaves ordenadas, voláteis removidos) |
| `compute_hash()` | SHA-256 de qualquer dict canônico |
| `merge_policies()` | Deep merge respeitando hierarquia de scope (global < group < device) |
| `detect_drift()` | Diff categorizado → gera sub-comandos granulares por categoria |

### `DriftDetector` — Orquestrador de Compliance

| Função | Responsabilidade |
|---|---|
| `evaluate_compliance()` | Estado desejado → compara hash → despacha sub-comandos |
| `handle_subcommand_result()` | Sucesso → compliant, falha repetida → `failed_loop` (anti-brick) |

**Proteções:**
- Rate limit: máximo 10 enforcements/hora por dispositivo.
- Anti-loop: 3 falhas consecutivas no mesmo sub-comando → bloqueio.

---

## Watchdogs (Tarefas em Background)

Três watchdogs concorrentes garantem a resiliência do sistema:

| Watchdog | Intervalo | Função |
|---|---|---|
| **Presença** | 30s | Marca dispositivos offline se heartbeat > 65s |
| **Timeout de Comandos** | 15s | Retry com backoff exponencial, DLQ após max_retries |
| **Compliance** | 5min | Reavalia devices sem check de compliance > 1 hora |

---

## Referência da API

### Autenticação

| Endpoint | Método | Auth | Descrição |
|---|---|---|---|
| `/api/auth/login` | POST | — | Login com email/senha → JWT |
| `/api/auth/register` | POST | Admin | Criar novo usuário |

### Dispositivos

| Endpoint | Método | Auth | Descrição |
|---|---|---|---|
| `/api/enroll` | POST | Bootstrap Secret | Enrollment do dispositivo Android |
| `/api/devices` | GET | JWT | Listar todos os dispositivos |
| `/api/devices/summary` | GET | JWT | Contadores (online, offline, locked) |
| `/api/devices/{id}` | GET | JWT | Detalhes do dispositivo |
| `/api/devices/{id}` | DELETE | JWT (Admin) | Remover dispositivo |
| `/api/devices/{id}/bootstrap` | GET | X-Device-Token | Download do SSOT |
| `/api/devices/{id}/status` | POST | X-Device-Token | Report de saúde |
| `/api/devices/{id}/telemetry` | GET | JWT | Dados de telemetria |
| `/api/devices/{id}/policy/sync` | POST | X-Device-Token | Handshake de drift detection |
| `/api/devices/{id}/commands` | GET | JWT | Histórico de todas as operações |
| `/api/devices/{id}/commands/pending` | GET | X-Device-Token | Buscar comandos pendentes |
| `/api/devices/{id}/commands/{cmd_id}/ack` | POST | X-Device-Token | Confirmar execução |
| `/api/devices/{id}/commands` | POST | JWT (Admin) | Criar comando remoto na fila |
| `/api/devices/{id}/lock` | POST | JWT (Admin) | Bloquear dispositivo |
| `/api/devices/{id}/reboot` | POST | JWT (Admin) | Reiniciar dispositivo |
| `/api/devices/{id}/wipe` | POST | JWT (Admin) | Factory reset |
| `/api/checkin` | POST | X-Device-Token | Check-in de telemetria periódico |

### Trust e Atestação

| Endpoint | Método | Auth | Descrição |
|---|---|---|---|
| `/api/devices/nonce` | GET | X-Device-Token | Gerar nonce assinado |
| `/api/devices/attest` | POST | X-Device-Token | Verificar integridade de hardware |

### WebSocket

| Endpoint | Protocolo | Descrição |
|---|---|---|
| `/api/ws/device/{device_id}` | WS | Canal device ↔ backend em tempo real |
| `/api/ws/dashboard?token=` | WS | Canal de broadcast para dashboard |

> Documentação interativa completa disponível em `http://<IP>:8200/docs` (Swagger UI) com o servidor rodando.

---

## Arquitetura de Segurança

### Autenticação de Dispositivos

Os dispositivos se autenticam via **token opaco** (não JWT). O token é gerado no enrollment e armazenado como hash SHA-256 no banco. O dispositivo envia o token no header `X-Device-Token` em cada requisição.

### Schemas de Dados do Redis

| Tipo | Padrão da Chave | TTL | Propósito |
|---|---|---|---|
| Nonce | `nonce:{tenant_id}:{request_id}` | 5 min | Anti-replay + binding |
| Cache de Veredito | `verdict_cache:{device_id}:v{version}` | 10–12 min (jitter) | Performance da API Google |
| Rate Limit | `rate_limit:{actor_id}:{path}` | 1 min | Hardening da API |
| Rastreio de Cmd | `cmd_track:{command_id}` | 1 hora | Ciclo de vida do Kill Switch |

### Camadas de Proteção

| Camada | Mecanismo | Descrição |
|---|---|---|
| Anti-Replay | Redis UNUSED→USED | Transição de estado do nonce preservando TTL |
| Binding | HMAC-SHA256 | Nonce vinculado a device + tenant + request |
| Clock Skew | ±60 segundos | Tolerância para dessincronização de relógio |
| Cache Stampede | Jitter TTL | TTL ± random(0–2min) previne thundering herd |
| CORS | Origins explícitas | Sem wildcard em produção |
| Rate Limiting | SlowAPI | 5 req/min no endpoint de enrollment |
| Escalação de Privilégios | Serviço RBAC | Admin não pode criar Super Admin |

---

## Observabilidade

### Logging Estruturado
- Formato: JSON com `event_type`, `correlation_id`, `device_id`.
- Tipos de evento: `ATTESTATION`, `POLICY_APPLY`, `COMMAND`, `ENROLLMENT`.

### Métricas Prometheus

| Métrica | Tipo | Descrição |
|---|---|---|
| `mdm_attestation_latency_ms` | Histogram | Latência da verificação Play Integrity |
| `mdm_policy_apply_total` | Counter | Taxa de sucesso de aplicação de políticas |
| `mdm_device_health_score` | Gauge | Último Compliance Score reportado |
| `mdm_commands_inflight` | Gauge | Comandos pendentes do estado VERIFIED |

---

## Setup Local

```bash
# Via Docker (recomendado)
docker compose up backend -d
# → API disponível em http://localhost:8200

# Ou diretamente (desenvolvimento sem Docker)
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8200 --reload
```

### Variáveis de Ambiente

| Variável | Obrigatória | Propósito |
|---|---|---|
| `DATABASE_URL` | ✅ | String de conexão AsyncPG |
| `SECRET_KEY` | ✅ | Chave de assinatura JWT |
| `BOOTSTRAP_SECRET` | ✅ | Autenticação de enrollment |
| `DB_PASSWORD` | ✅ | Senha do PostgreSQL |
| `REDIS_HOST` | ○ | Hostname do Redis (padrão: `redis` no Docker) |
| `ENVIRONMENT` | ○ | `development` / `production` |
| `API_URL` | ○ | URL pública do backend (ex: `http://192.168.25.227:8200`) |
| `ALLOWED_ORIGINS` | ○ (✅ prod) | Origins CORS permitidas |

> Veja [`.env.example`](../.env.example) para a referência completa.
