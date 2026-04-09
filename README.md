<p align="center">
  <h1 align="center">🛡️ Elion MDM</h1>
  <p align="center">
    <strong>Plataforma Enterprise de Gerenciamento de Dispositivos Móveis</strong>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi" alt="FastAPI" />
    <img src="https://img.shields.io/badge/Frontend-React+Vite-61DAFB?style=for-the-badge&logo=react" alt="React" />
    <img src="https://img.shields.io/badge/Mobile-Kotlin-7F52FF?style=for-the-badge&logo=kotlin" alt="Kotlin" />
    <img src="https://img.shields.io/badge/DB-PostgreSQL-4169E1?style=for-the-badge&logo=postgresql" alt="PostgreSQL" />
    <img src="https://img.shields.io/badge/Cache-Redis-DC382D?style=for-the-badge&logo=redis" alt="Redis" />
    <img src="https://img.shields.io/badge/Infra-Docker-2496ED?style=for-the-badge&logo=docker" alt="Docker" />
  </p>
</p>

---

## Visão Geral

O Elion MDM é uma plataforma full-stack para gerenciamento de frotas de dispositivos Android corporativos. Entrega provisionamento zero-touch, execução de comandos em tempo real, enforcement contínuo de compliance e verificação de confiança vinculada ao hardware — do enrollment até o descomissionamento.

| Capacidade | Descrição |
|---|---|
| **Enrollment Zero-Touch** | Provisionamento via QR Code — sem interação manual |
| **Comandos em Tempo Real** | WebSocket bidirecional para LOCK, WIPE, INSTALL |
| **Drift Detection** | Comparação de hash SHA-256 para desvio de conformidade |
| **Self-Healing** | State machine com backoff exponencial (anti-brick) |
| **Trust de Hardware** | Play Integrity API para atestação do dispositivo |
| **Compliance Scoring** | Score ponderado (0–100) com enforcement automático |
| **RBAC** | Controle de acesso por roles com anti-escalação de privilégios |
| **Observabilidade** | Logs JSON estruturados + métricas Prometheus |

---

## Arquitetura do Sistema

```
┌──────────────┐     ┌──────────────────────────┐     ┌──────────────────┐
│   Android    │◄───►│     Nginx Reverse Proxy   │◄───►│  React Dashboard │
│   Agent      │     │  TLS · WS Upgrade · LB    │     │  (Vite + TS)     │
│   (Kotlin)   │     └────────────┬──────────────┘     └──────────────────┘
└──────────────┘                  │
                      ┌───────────▼───────────┐
                      │    FastAPI Backend     │
                      │  Serviços · Watchdogs  │
                      └───┬──────────────┬────┘
                          │              │
                    ┌─────▼───┐    ┌─────▼────┐    ┌──────────────────┐
                    │Postgres │    │  Redis   │    │ Google Play      │
                    │   DB    │    │  Cache   │    │ Integrity API    │
                    └─────────┘    └──────────┘    └──────────────────┘
```

---

## Documentação por Módulo

| Módulo | README | Descrição |
|---|---|---|
| **Backend** | [`backend/README.md`](backend/README.md) | API, serviços, watchdogs, modelos de dados |
| **Frontend** | [`frontend/README.md`](frontend/README.md) | Dashboard, hooks WebSocket, componentes |
| **Android Agent** | [`android/README.md`](android/README.md) | State machine, DPM, segurança, comandos |

---

## Início Rápido

```bash
# 1. Clone e configure
git clone https://github.com/oblivius321/MDM_PROJECT_ELION.git
cd MDM_PROJECT_ELION
cp .env.example .env  # Preencha com valores seguros

# 2. Suba a stack
docker compose up -d

# 3. Crie o usuário admin
docker compose exec backend python -m backend.create_admin

# 4. Acesse
#    Dashboard  → http://localhost
#    API Docs   → http://localhost:8000/docs
#    Métricas   → http://localhost:8000/metrics
```

> Para deploy em produção, veja [Deploy em Produção](#deploy-em-produção) abaixo.

---

## Infraestrutura

| Serviço | Porta | Função |
|---|---|---|
| **Nginx** | `:80` | Terminação TLS, upgrade WS, proxy reverso |
| **Backend** | `:8000` | FastAPI + Uvicorn (atrás do Nginx) |
| **Frontend** | `:3000` | Servidor dev Vite (atrás do Nginx) |
| **PostgreSQL** | `:5432` | Armazenamento primário de dados |
| **Redis** | `:6379` | Anti-replay de nonces, cache de vereditos, rate limiting |

---

## Deploy em Produção

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**Variáveis de ambiente obrigatórias em produção:**

| Variável | Propósito |
|---|---|
| `SECRET_KEY` | Assinatura JWT (32+ caracteres) |
| `BOOTSTRAP_SECRET` | Segredo de enrollment de dispositivos |
| `ATTESTATION_SECRET` | Chave HMAC para nonces |
| `DB_PASSWORD` | Senha do PostgreSQL |
| `ALLOWED_ORIGINS` | Origins CORS explícitas (sem wildcard) |

> Gere segredos com: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

---

## Roadmap

### Capacidades Atuais
- Enrollment Zero-Touch via QR Code com Bootstrap SSOT
- Comunicação híbrida (WebSocket + fallback por polling)
- Enforcement determinístico de políticas com drift detection
- Atestação de hardware via Play Integrity API
- Compliance scoring com enforcement automático
- Pipeline DevSecOps CI/CD (Bandit, Trivy, pip-audit)

### Em Progresso
- Isolamento multi-tenant SaaS

### Roadmap Futuro
- Orquestração Kubernetes (EKS/GKE)
- Agente iOS (Swift)
- Dashboards de observabilidade Grafana + Loki
- Suporte Work Profile (BYOD)

---

## Licença

Proprietário — Todos os direitos reservados.

<p align="center">
  <sub>Desenvolvido pela Equipe de Segurança Elion · MDM Enterprise · Arquitetura Zero Trust</sub>
</p>
