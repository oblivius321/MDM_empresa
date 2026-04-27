<p align="center">
  <h1 align="center">Elion MDM</h1>
  <p align="center">
    <strong>Plataforma enterprise de gerenciamento de dispositivos moveis</strong>
  </p>
</p>

---

## Visão Geral

O Elion MDM é uma plataforma full-stack para gerenciamento de dispositivos Android corporativos. O projeto combina um dashboard web em React, backend FastAPI assíncrono, agente Android nativo e serviços de observabilidade.

| Capacidade | Descrição |
|---|---|
| Enrollment via ADB | Provisionamento manual com Bootstrap Secret |
| Telemetria Rica | Bateria, GPS, apps instalados, armazenamento e app em foreground |
| Comandos Stateful | Execucao de comandos com acompanhamento de ciclo de vida (ACK → EXECUTED → VERIFIED) |
| Drift Detection | Comparacao de hash SHA-256 para detectar desvio de conformidade |
| Self-Healing | Rotinas de remediacao com backoff controlado e circuit breaker |
| Trust de Hardware | Integracao com Play Integrity API |
| Compliance Scoring | Score ponderado com enforcement automatico |
| RBAC | Controle de acesso por roles e permissoes granulares |
| Observabilidade | Logs estruturados JSON e metricas Prometheus |
| Comunicacao Dupla | WebSocket em tempo real + REST polling como fallback |

---

## Arquitetura

O sistema opera com **exposicao direta de servicos** — sem proxy reverso. O backend FastAPI e o frontend React sao acessados diretamente nas suas respectivas portas.

```text
                    ┌──────────────────────┐
                    │   Dashboard React    │
                    │    (porta 3000)      │
                    └──────────┬───────────┘
                               │ REST + WebSocket
                               ▼
┌──────────┐        ┌──────────────────────┐
│ Android  │◄──────►│   FastAPI Backend    │
│  Agent   │  HTTP  │    (porta 8200)      │
│  (APK)   │  + WS  └──────────┬───────────┘
└──────────┘                   │
                    ┌──────────┴───────────┐
                    │                      │
              ┌─────▼─────┐         ┌──────▼─────┐
              │PostgreSQL │         │   Redis    │
              │  (5432)   │         │   (6379)   │
              └───────────┘         └────────────┘
```

**Nota:** Nao ha Nginx ou qualquer proxy reverso na stack. O backend (Uvicorn) e exposto diretamente na porta `8200` do host, e o frontend (Vite/serve) na porta `3000`.

---

## Documentacao por Modulo

| Modulo | README | Descricao |
|---|---|---|
| Backend | [`backend/README.md`](backend/README.md) | API, servicos, watchdogs, seguranca e modelos |
| Frontend | [`frontend/README.md`](frontend/README.md) | Dashboard, hooks WebSocket e componentes |
| Android Agent | [`android/README.md`](android/README.md) | Foreground service, state machine, DPM e comandos |

### Documentacao Adicional

| Documento | Descricao |
|---|---|
| [`docs/instalando_apk.md`](docs/instalando_apk.md) | Guia de instalacao do APK via ADB |
| [`docs/RBAC_IMPLEMENTATION.md`](docs/RBAC_IMPLEMENTATION.md) | Arquitetura do sistema RBAC |
| [`docs/android-management-api.md`](docs/android-management-api.md) | Integracao com AMAPI do Google |

---

## Inicio Rapido

### Pre-requisitos

- Docker e Docker Compose instalados
- Porta `8200`, `3000`, `5432` e `6379` livres no host

### Subindo o ambiente

```bash
# 1. Clone e configure
git clone https://github.com/oblivius321/MDM_PROJECT_ELION.git
cd MDM_PROJECT_ELION
cp .env.example .env
# Edite o .env com suas senhas e IP do servidor

# 2. Suba a stack
docker compose up -d

# 3. Acesse
#    Dashboard  -> http://<SEU_IP>:3000
#    API Docs   -> http://<SEU_IP>:8200/docs
#    Metricas   -> http://<SEU_IP>:8200/metrics
```

> Para deploy em producao, use `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`.

---

## Infraestrutura

| Servico | Container | Porta Host | Funcao |
|---|---|---|---|
| Backend | `elion-mdm-backend` | `8200` | FastAPI + Uvicorn (exposto diretamente, sem proxy) |
| Frontend | `elion-mdm-frontend` | `3000` | Dashboard React/Vite |
| PostgreSQL | `elion-mdm-postgres` | `5432` | Armazenamento primario |
| Redis | `elion-mdm-redis` | `6379` | Cache, anti-replay, rate limiting e tokens de enrollment |

> **Sem Nginx:** Todos os servicos sao acessados diretamente nas portas listadas. O backend mapeia a porta interna `8000` para `8200` no host via Docker.

---

## Variaveis de Ambiente Importantes

| Variavel | Proposito |
|---|---|
| `SECRET_KEY` | Assinatura JWT |
| `BOOTSTRAP_SECRET` | Segredo de enrollment (usado pelo agente Android) |
| `DB_PASSWORD` | Senha do PostgreSQL |
| `API_URL` | URL publica do backend (ex: `http://192.168.25.227:8200`) |
| `ALLOWED_ORIGINS` | Lista explicita de origens CORS (sem wildcard em producao) |
| `DEFAULT_ADMIN_PASSWORD` | Senha do admin padrao criado na inicializacao |

> Veja [`.env.example`](.env.example) para a referencia completa e [`.env.production.example`](.env.production.example) para producao.

---

## Fluxo de Enrollment (ADB Manual)

O enrollment atual utiliza **instalacao manual via ADB** com Bootstrap Secret:

```text
1. Admin gera o Bootstrap Secret no .env
2. Instala o APK no dispositivo via ADB:
   adb install -r elion-mdm.apk
3. Abre o app e insere:
   - URL do backend (ex: http://192.168.25.227:8200)
   - Bootstrap Secret
4. O agente registra o dispositivo e inicia o servico de telemetria
5. O dispositivo aparece no dashboard automaticamente
```

> Para detalhes completos, veja [`docs/instalando_apk.md`](docs/instalando_apk.md).

---

## Roadmap

### Capacidades Atuais
- Enrollment manual via ADB com Bootstrap Secret
- Telemetria rica (bateria, GPS, apps, armazenamento, foreground app)
- Pipeline de comandos assincronos com ciclo de vida stateful
- Enforcement de politicas com drift detection
- Atestacao de hardware via Play Integrity
- Compliance scoring com enforcement automatico
- RBAC com roles e permissoes granulares
- Comunicacao dupla: WebSocket + REST polling

### Em Progresso
- Isolamento multi-tenant SaaS


### Futuro
- Orquestracao Kubernetes
- Observabilidade com Grafana + Loki
- Suporte Work Profile (BYOD)
- Enrollment via QR Code (Device Owner)

---

## Licenca

Proprietario. Todos os direitos reservados.
