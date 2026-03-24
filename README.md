<p align="center">
  <img src="https://img.shields.io/badge/Elion-MDM-0D1117?style=for-the-badge&logo=android&logoColor=3DDC84&labelColor=161B22" alt="Elion MDM"/>
</p>

<h1 align="center">🛡️ Elion MDM</h1>

<p align="center">
  <strong>Enterprise Mobile Device Management Platform</strong><br/>
  <em>Gerencie, proteja e controle dispositivos Android corporativos em escala.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Frontend-React_18-61DAFB?style=flat-square&logo=react&logoColor=white" alt="React"/>
  <img src="https://img.shields.io/badge/Mobile-Kotlin-7F52FF?style=flat-square&logo=kotlin&logoColor=white" alt="Kotlin"/>
  <img src="https://img.shields.io/badge/Database-PostgreSQL_15-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/Infra-Docker-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"/>
  <img src="https://img.shields.io/badge/Proxy-Nginx-009639?style=flat-square&logo=nginx&logoColor=white" alt="Nginx"/>
</p>

---

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Arquitetura](#-arquitetura)
- [Stack Tecnológica](#-stack-tecnológica)
- [Funcionalidades](#-funcionalidades)
- [Quick Start](#-quick-start)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Configuração](#-configuração)
- [Comandos Docker](#-comandos-docker)
- [Android DPC Agent](#-android-dpc-agent)
- [Segurança](#-segurança)
- [Deploy em Produção](#-deploy-em-produção-vps)
- [Troubleshooting](#-troubleshooting)
- [Licença](#-licença)

---

## 🌐 Visão Geral

**Elion MDM** é uma plataforma completa de gerenciamento de dispositivos móveis (MDM) projetada para ambientes corporativos. O sistema permite que administradores de TI controlem, monitorem e protejam dispositivos Android de forma centralizada.

### O que o Elion faz?

| Capacidade | Descrição |
|------------|-----------|
| 🔒 **Lockdown de Dispositivos** | Kiosk mode, bloqueio de câmera, status bar, factory reset |
| 📊 **Monitoramento em Tempo Real** | Telemetria via WebSocket, bateria, compliance |
| 📱 **Gerenciamento de Apps** | Controle de apps permitidos, instalação silenciosa de APKs |
| 📜 **Políticas de Segurança** | Criação e aplicação de políticas em massa |
| 👥 **RBAC Completo** | Roles, permissions, audit log, multi-admin |
| 🔐 **Kiosk Launcher Endurecido** | HOME app com Lock Task, anti-escape, anti-tampering |
| 🌐 **Comandos Remotos** | Lock, wipe, reboot, kiosk via WebSocket ou polling |

---

## 🏗 Arquitetura

```
                      Internet / Administrador
                              │
                 ┌────────────▼────────────┐
                 │    Nginx Reverse Proxy   │  :80 / :443
                 │   (rate limit, TLS, CORS)│
                 └─────┬──────────┬────────┘
                       │          │
          ┌────────────▼──┐  ┌───▼─────────────┐
          │   Frontend    │  │   Backend API   │
          │ React + Vite  │  │  FastAPI + WS   │
          │  TypeScript   │  │  SQLAlchemy     │
          │   :3000       │  │    :8000        │
          └───────────────┘  └───────┬─────────┘
                                     │
                        ┌────────────▼──────────┐
                        │  PostgreSQL 15        │
                        │  (async via asyncpg)  │
                        └───────────────────────┘

    ┌──────────────────────────────────────────────┐
    │           Android Devices (Field)            │
    │  ┌─────────────────────────────────────────┐ │
    │  │  Elion DPC Agent (Kotlin)               │ │
    │  │  • Device Owner / Lock Task Mode        │ │
    │  │  • Kiosk Launcher (HOME app)            │ │
    │  │  • Check-in periódico + WebSocket       │ │
    │  │  • Encrypted storage (AES-256)          │ │
    │  └─────────────────────────────────────────┘ │
    └──────────────────────────────────────────────┘
```

### Roteamento Nginx

| Rota | Destino | Descrição |
|------|---------|-----------|
| `/` | Frontend | Console web React |
| `/api/*` | Backend | REST API |
| `/ws` | Backend | WebSocket tempo real |
| `/health` | Nginx | Health check |

---

## 🔧 Stack Tecnológica

### Backend

| Componente | Tecnologia |
|-----------|------------|
| Framework | **FastAPI** (Python 3.11) |
| ORM | **SQLAlchemy 2.0** (async) |
| Database | **PostgreSQL 15** (asyncpg) |
| Auth | **JWT** (python-jose + bcrypt) |
| Rate Limiting | **SlowAPI** |
| Validation | **Pydantic** |
| Real-time | **WebSockets** (nativo FastAPI) |

### Frontend

| Componente | Tecnologia |
|-----------|------------|
| Framework | **React 18** (TypeScript) |
| Build Tool | **Vite 5** |
| Styling | **Tailwind CSS** + **shadcn/ui** |
| Data Fetching | **TanStack React Query** |
| Charts | **Recharts** |
| Forms | **React Hook Form** + **Zod** |
| HTTP Client | **Axios** |
| Routing | **React Router 6** |

### Android Agent

| Componente | Tecnologia |
|-----------|------------|
| Linguagem | **Kotlin** |
| Min SDK | **30** (Android 11) |
| Target SDK | **35** (Android 15) |
| Networking | **Retrofit** + **OkHttp** |
| Storage | **EncryptedSharedPreferences** (AES-256-GCM) |
| Device Control | **DevicePolicyManager** (Device Owner) |
| Kiosk | **Lock Task Mode** |

### Infraestrutura

| Componente | Tecnologia |
|-----------|------------|
| Containers | **Docker Compose** |
| Proxy | **Nginx** (reverse proxy + rate limit + TLS) |
| TLS | **Let's Encrypt** (Certbot) |

---

## ✨ Funcionalidades

### 🖥️ Console Web (Frontend)

- **Dashboard** — visão geral de dispositivos, compliance, gráficos
- **Dispositivos** — lista com busca, filtros e detalhes
- **Detalhe do Dispositivo** — telemetria, envio de comandos (lock, wipe, reboot, kiosk)
- **Políticas** — criação e gestão de políticas de segurança (câmera, kiosk, PIN, etc.)
- **Logs de Auditoria** — rastreamento de todas as ações (RBAC audit trail)
- **Configurações** — gerenciamento de administradores, perfil
- **Login** — autenticação JWT com recuperação de senha e pergunta de segurança

### ⚙️ API Backend

- **Auth** — login/registro com JWT, rate limiting, password recovery
- **Enrollment** — onboarding de dispositivos com bootstrap secret
- **Device Management** — CRUD de dispositivos, telemetria, check-in
- **Command Queue** — fila de comandos com ACK (lock, wipe, reboot, kiosk, install APK)
- **Policy Engine** — criação/aplicação de políticas por dispositivo
- **RBAC** — roles, permissions, assignment, audit log
- **WebSocket** — push notifications para dispositivos em tempo real

### 📱 Android DPC Agent

- **Device Owner** — controle total do dispositivo via DPM
- **Kiosk Launcher** — HOME app customizado com grid de apps permitidos
- **Lock Task Mode** — lockdown completo (home, back, recents desabilitados)
- **Anti-Tampering** — watchdog de segurança a cada 15s com auto-recovery
- **Admin Panel** — login seguro + painel de controle local (em português)
- **Brute-Force Protection** — 5 tentativas, lockout exponencial (30s→480s)
- **Boot Persistence** — reaplica kiosk automaticamente no reboot
- **Check-in** — telemetria periódica (bateria, compliance, modelo)
- **WebSocket** — recebimento de comandos em tempo real
- **Encrypted Storage** — AES-256-GCM via Android Keystore

---

## 🚀 Quick Start

### Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) ou Docker Engine (Linux)
- [Git](https://git-scm.com/)

### 1. Clonar e configurar

```bash
git clone https://github.com/oblivius321/MDM_PROJECT_ELION.git
cd MDM_PROJECT_ELION

# Criar arquivo de configuração
cp .env.example .env
# Editar .env com suas senhas
```

### 2. Subir o sistema

```powershell
# Windows PowerShell (helper script)
.\start_docker.ps1

# Ou diretamente via Docker Compose
docker compose up -d
```

### 3. Criar administrador

```bash
docker compose exec backend python -m backend.create_admin \
  --email admin@mdm.com \
  --password SuaSenhaForte123!
```

### 4. Acessar

| Serviço | URL |
|---------|-----|
| 🖥️ Console Web (Vite) | http://localhost:3000 |
| 🌐 Console Web (Nginx) | http://localhost |
| 📡 API REST | http://localhost/api |
| 📖 Swagger Docs | http://localhost/api/docs |
| 🗄️ PostgreSQL | `localhost:5432` |

---

## 📁 Estrutura do Projeto

```
MDM_PROJECT_ELION/
│
├── 🐍 backend/                    # API FastAPI
│   ├── api/
│   │   ├── auth.py                # Login, registro, password recovery
│   │   ├── routes.py              # Device CRUD, commands, policies
│   │   ├── rbac_routes.py         # Roles, permissions, audit
│   │   ├── device_auth.py         # Device enrollment auth
│   │   ├── websocket_routes.py    # WebSocket endpoints
│   │   └── websockets.py          # WS connection manager
│   ├── core/
│   │   ├── database.py            # SQLAlchemy async engine
│   │   ├── security.py            # JWT, bcrypt, token handling
│   │   └── limiter.py             # SlowAPI rate limiter
│   ├── models/
│   │   ├── user.py                # User model (admin)
│   │   ├── device.py              # Device model
│   │   ├── policy.py              # Policy model
│   │   ├── telemetry.py           # Telemetry model
│   │   ├── role.py                # RBAC role model
│   │   ├── permission.py          # RBAC permission model
│   │   └── audit_log.py           # Audit trail model
│   ├── repositories/              # Data access layer (Repository Pattern)
│   ├── schemas/                   # Pydantic validation schemas
│   ├── services/
│   │   ├── mdm_service.py         # Device management business logic
│   │   └── rbac_service.py        # RBAC business logic
│   ├── utils/
│   │   ├── decorators.py          # Auth/RBAC decorators
│   │   └── rbac_constants.py      # Permission constants
│   ├── main.py                    # App entrypoint
│   └── create_admin.py            # CLI para criar admin
│
├── ⚛️  frontend/                   # Console Web React
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx      # Dashboard principal
│   │   │   ├── Devices.tsx        # Lista de dispositivos
│   │   │   ├── DeviceDetail.tsx   # Detalhes + comandos
│   │   │   ├── Policies.tsx       # Gestão de políticas
│   │   │   ├── Logs.tsx           # Audit logs
│   │   │   ├── Settings.tsx       # Configurações
│   │   │   └── Login.tsx          # Autenticação
│   │   ├── components/
│   │   │   ├── AppSidebar.tsx     # Navegação lateral
│   │   │   ├── TopBar.tsx         # Barra superior
│   │   │   ├── PrivateRoute.tsx   # Route guard
│   │   │   ├── ForgotPassword.tsx # Recovery de senha
│   │   │   └── ui/               # shadcn/ui components
│   │   ├── contexts/
│   │   │   └── AuthContext.tsx    # Auth state management
│   │   └── services/
│   │       └── api.ts             # Axios client
│   ├── Dockerfile                 # Multi-stage (dev + prod)
│   └── vite.config.ts             # Proxy /api → backend
│
├── 🤖 android/                     # DPC Agent (Kotlin)
│   ├── KioskLauncherActivity.kt   # HOME app (Lock Task)
│   ├── AdminLoginActivity.kt     # Login admin seguro
│   ├── AdminPanelActivity.kt     # Painel admin (PT-BR)
│   ├── KioskManager.kt           # Orquestrador do kiosk
│   ├── KioskSecurityManager.kt   # Watchdog anti-tampering
│   ├── AdminAuthManager.kt       # Auth + brute-force
│   ├── AdminReceiver.kt          # Device Owner receiver
│   ├── BootReceiver.kt           # Auto-start no boot
│   ├── DevicePolicyHelper.kt     # Abstração DPM
│   ├── MDMForegroundService.kt   # Foreground service (check-in + WS)
│   ├── CommandHandler.kt         # Executor de comandos remotos
│   ├── SecurePreferences.kt      # EncryptedSharedPreferences
│   ├── ApiClient.kt              # Retrofit + OkHttp
│   ├── ApiService.kt             # API endpoints
│   ├── ApiModels.kt              # DTOs (Gson)
│   ├── AndroidManifest.xml       # Manifest com HOME filter
│   ├── activity_kiosk_launcher.xml
│   ├── activity_admin_login.xml
│   ├── activity_admin_panel.xml
│   └── build.gradle.kts          # Gradle config
│
├── 🗃️  migrations/                 # SQL migration scripts
│   ├── 001_add_security_question.sql
│   ├── 002_add_password_reset_fields.sql
│   └── 003_create_rbac_tables.sql
│
├── 🐳 docker-compose.yml          # Dev environment
├── 🐳 docker-compose.prod.yml     # Production overrides
├── 🐳 Dockerfile.backend          # Multi-stage backend
├── 🔀 nginx.conf                  # Reverse proxy + security
├── 📝 .env.example                # Dev env template
├── 📝 .env.production.example     # Prod env template
├── 🛡️  ssl/                        # TLS certificates
├── 📜 start_docker.ps1            # PowerShell helper
└── 📦 requirements.txt            # Python dependencies
```

---

## ⚙️ Configuração

### Variáveis de Ambiente

| Variável | Descrição | Obrigatória |
|----------|-----------|:-----------:|
| `DB_PASSWORD` | Senha do PostgreSQL | ✅ |
| `SECRET_KEY` | Chave para tokens JWT | ✅ |
| `BOOTSTRAP_SECRET` | Chave para enrollment de dispositivos | ✅ |
| `DEFAULT_ADMIN_PASSWORD` | Senha inicial do admin | ✅ |
| `DB_USER` | Usuário do banco | ❌ (default: postgres) |
| `DB_NAME` | Nome do banco | ❌ (default: mdm_project) |
| `ALLOWED_ORIGINS` | CORS origins (produção) | ⚠️ em prod |
| `ENVIRONMENT` | `development` ou `production` | ❌ |

### Gerar chaves seguras

```python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 🐳 Comandos Docker

### Operações Básicas

```bash
docker compose up -d              # Subir containers
docker compose down               # Parar
docker compose down -v            # Parar + reset banco
docker compose up -d --build      # Rebuild
docker compose logs -f            # Logs tempo real
docker compose logs -f backend    # Logs do backend
```

### PowerShell Helper (Windows)

```powershell
.\start_docker.ps1                # Subir dev
.\start_docker.ps1 -Build         # Rebuild
.\start_docker.ps1 -Down          # Parar
.\start_docker.ps1 -Logs          # Logs
.\start_docker.ps1 -Clean         # Limpar tudo
.\start_docker.ps1 -CreateAdmin   # Criar admin
.\start_docker.ps1 -Prod          # Modo produção
```

### Acessar Containers

```bash
docker compose exec backend bash                              # Shell backend
docker compose exec postgres psql -U postgres -d mdm_project  # psql
docker compose exec frontend sh                                # Shell frontend
```

---

## 🤖 Android DPC Agent

### Setup do Device Owner

```bash
# 1. Instalar o APK no dispositivo
adb install elion-mdm.apk

# 2. Definir como Device Owner (requer factory reset prévio)
adb shell dpm set-device-owner com.elion.mdm/.AdminReceiver

# 3. Verificar
adb shell dpm list-owners
```

### Modo Kiosk

O Kiosk Launcher funciona como o launcher padrão do Android (HOME app), trancando o usuário nos aplicativos permitidos:

| Proteção | Mecanismo |
|----------|-----------|
| Lock Task Mode | `startLockTask()` — desabilita Home, Back, Recents |
| Status Bar | `setStatusBarDisabled(true)` — impede acesso às notificações |
| Keyguard | `setKeyguardDisabled(true)` — sem tela de bloqueio |
| Factory Reset | `DISALLOW_FACTORY_RESET` — bloqueado |
| USB | `DISALLOW_USB_FILE_TRANSFER` — sem transferência |
| Install/Uninstall | `DISALLOW_INSTALL_APPS` / `DISALLOW_UNINSTALL_APPS` |
| Anti-Tampering | Watchdog a cada 15s verifica e reaplica restrições |
| Boot Persistence | `BootReceiver` reativa kiosk ao ligar o dispositivo |
| Admin Auth | Login com brute-force protection (5 tentativas, lockout exponencial) |

### Painel Admin (no dispositivo)

| Opção | Função |
|-------|--------|
| 🔒 Ativar/Desativar Modo Kiosk | Toggle via KioskManager |
| 📶 Configurações de Wi-Fi | Abre settings de Wi-Fi |
| 🔊 Controle de Volume | SeekBar de volume |
| 🚫 Bloquear Barra de Status | Toggle via DPM |
| 📱 Gerenciar Aplicativos | Seleção de apps permitidos |
| 🔄 Sincronizar com Servidor | Sync manual |
| ℹ️ Informações do Dispositivo | Model, Android, DO status |
| 🚪 Sair do modo Kiosk | Requer re-autenticação |

---

## 🔐 Segurança

### Backend

- ✅ Backend **não exposto** ao host — Nginx faz proxy reverso
- ✅ **Rate limiting** (API: 10r/s, Auth: 5r/min)
- ✅ **Security headers** (X-Frame-Options, X-Content-Type-Options, CSP)
- ✅ **JWT** com expiração + bcrypt para senhas
- ✅ **CORS** com origins explícitas (sem wildcard)
- ✅ **Trusted Host** middleware contra Host Header attacks
- ✅ PostgreSQL isolado na rede Docker
- ✅ Container backend roda como **non-root**
- ✅ **RBAC** completo com audit trail

### Android

- ✅ **EncryptedSharedPreferences** (AES-256-GCM via Android Keystore)
- ✅ **Lock Task Mode** — impossível sair sem autorização Device Owner
- ✅ **Anti-tampering watchdog** — monitoramento contínuo
- ✅ **Brute-force** — lockout exponencial após 5 tentativas
- ✅ **Session timeout** — 5 minutos de inatividade
- ✅ `allowBackup="false"` — sem backup ADB
- ✅ **Boot receiver** — reaplica políticas automaticamente

---

## 🚀 Deploy em Produção (VPS)

### 1. Preparar o servidor

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

### 2. Clonar e configurar

```bash
git clone https://github.com/oblivius321/MDM_PROJECT_ELION.git /opt/elion-mdm
cd /opt/elion-mdm

cp .env.production.example .env
nano .env  # Editar com senhas fortes de produção
```

### 3. Certificados TLS (Let's Encrypt)

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d seu-dominio.com

sudo cp /etc/letsencrypt/live/seu-dominio.com/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/seu-dominio.com/privkey.pem ./ssl/
```

### 4. Build e deploy

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### 5. Criar admin

```bash
docker compose exec backend python -m backend.create_admin \
  --email admin@sua-empresa.com \
  --password SenhaProducaoForte123!
```

### 6. Firewall

```bash
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### 7. Auto-renovação de certificados

```bash
echo "0 3 * * * certbot renew --quiet && docker compose restart nginx" | sudo crontab -
```

---

## 🐛 Troubleshooting

| Problema | Solução |
|----------|---------|
| "Connection refused" localhost | `docker compose ps` — verificar se estão UP |
| "ERR_NAME_NOT_RESOLVED" | Usar `localhost:3000`, não IP interno Docker |
| Backend 500 no login | `docker compose logs backend` — verificar DATABASE_URL |
| PostgreSQL não inicia | `docker compose down -v && docker compose up -d` |
| Frontend não atualiza | `docker compose restart frontend` ou limpar cache |
| Porta 80 ocupada | Alterar para 8080 no `docker-compose.yml` |
| Android: "Not Device Owner" | `adb shell dpm set-device-owner com.elion.mdm/.AdminReceiver` |
| Gradle JVM error | Atualizar para JDK 17+ no Android Studio |

---

## 📄 Licença

Este projeto é proprietário. Todos os direitos reservados.

---

<p align="center">
  <sub>Developed with ❤️ for enterprise security</sub><br/>
  <strong>Elion MDM</strong> — Protecting what matters.
</p>
