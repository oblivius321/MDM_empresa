# Elion MDM – Mobile Device Management

Sistema de gerenciamento de dispositivos móveis Android com painel web, API REST, WebSockets em tempo real e agente DPC Android.

---

## Arquitetura

```
                  Internet / Usuário
                        │
           ┌────────────▼────────────┐
           │   Nginx (reverse proxy) │  :80 / :443
           └─────┬──────────┬────────┘
                 │          │
    ┌────────────▼──┐  ┌───▼─────────────┐
    │   Frontend    │  │   Backend API   │
    │ React + Vite  │  │  FastAPI + WS   │
    │   :3000       │  │    :8000        │
    └───────────────┘  └───────┬─────────┘
                               │
                  ┌────────────▼──────────┐
                  │  PostgreSQL 15        │
                  │  :5432 (interno)      │
                  └───────────────────────┘
```

| Camada     | Stack                                                   |
|------------|---------------------------------------------------------|
| Frontend   | React 18, TypeScript, Vite 5, Tailwind CSS, shadcn/ui   |
| Backend    | Python 3.11, FastAPI, SQLAlchemy async, asyncpg, JWT    |
| Database   | PostgreSQL 15-alpine                                    |
| Proxy      | Nginx (rate limiting, security headers)                 |
| Mobile     | Kotlin, Android Enterprise DPC                          |

### Rotas do Nginx

| Caminho     | Destino                  |
|-------------|--------------------------|
| `/`         | Frontend (React)         |
| `/api/*`    | Backend (FastAPI)        |
| `/ws`       | Backend WebSocket        |
| `/api/ws/*` | Backend WebSocket        |
| `/health`   | Health check Nginx       |

---

## Quick Start (Desenvolvimento Local)

### Pré-requisitos

- Docker Desktop (Windows/Mac) ou Docker Engine (Linux)
- Git

### 1. Clonar e configurar

```bash
git clone <repo-url>
cd MDM_PROJETO

# Criar arquivo de configuração
cp .env.example .env
# Editar .env com suas senhas
```

### 2. Subir o sistema

```powershell
# Windows PowerShell
.\start_docker.ps1

# Ou diretamente via Docker Compose
docker compose up -d
```

### 3. Criar usuário administrador

```bash
docker compose exec backend python -m backend.create_admin \
  --email admin@mdm.com \
  --password SuaSenhaForte123!
```

### 4. Acessar

| Serviço             | URL                              |
|---------------------|----------------------------------|
| Frontend (Vite)     | http://localhost:3000             |
| Frontend (Nginx)    | http://localhost                  |
| API                 | http://localhost/api              |
| Swagger Docs        | http://localhost/api/docs         |
| PostgreSQL          | `localhost:5432`                  |

---

## Comandos Docker

### Operações Básicas

```bash
# Subir containers
docker compose up -d

# Parar containers
docker compose down

# Parar + remover volumes (reset banco)
docker compose down -v

# Rebuild imagens
docker compose up -d --build

# Ver logs em tempo real
docker compose logs -f

# Logs de um serviço específico
docker compose logs -f backend
```

### PowerShell Helper (Windows)

```powershell
.\start_docker.ps1              # Subir dev
.\start_docker.ps1 -Build       # Rebuild
.\start_docker.ps1 -Down        # Parar
.\start_docker.ps1 -Logs        # Logs
.\start_docker.ps1 -Clean       # Limpar tudo
.\start_docker.ps1 -CreateAdmin # Criar admin
.\start_docker.ps1 -Prod        # Modo produção
```

### Acessar containers

```bash
# Shell do backend
docker compose exec backend bash

# psql do banco
docker compose exec postgres psql -U postgres -d mdm_project

# Shell do frontend
docker compose exec frontend sh
```

---

## Configuração (.env)

### Variáveis Obrigatórias

| Variável               | Descrição                                 |
|------------------------|-------------------------------------------|
| `DB_PASSWORD`          | Senha do PostgreSQL                       |
| `SECRET_KEY`           | Chave para JWT (gerar com secrets module) |
| `BOOTSTRAP_SECRET`     | Chave para enrollment de dispositivos     |
| `DEFAULT_ADMIN_PASSWORD` | Senha do primeiro admin                 |

### Gerar chaves seguras

```python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Deploy em VPS (Linux)

### 1. Preparar o servidor

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# Logout e login novamente
```

### 2. Clonar e configurar

```bash
git clone <repo-url> /opt/elion-mdm
cd /opt/elion-mdm

cp .env.production.example .env
# Editar .env com senhas de produção fortes
nano .env
```

### 3. Certificados TLS (Let's Encrypt)

```bash
# Instalar certbot
sudo apt install certbot

# Gerar certificados
sudo certbot certonly --standalone -d seu-dominio.com

# Copiar para o projeto
sudo cp /etc/letsencrypt/live/seu-dominio.com/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/seu-dominio.com/privkey.pem ./ssl/

# Habilitar HTTPS no nginx.conf (descomentar bloco server 443)
```

### 4. Build e deploy de produção

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### 5. Criar admin no servidor

```bash
docker compose exec backend python -m backend.create_admin \
  --email admin@sua-empresa.com \
  --password SenhaProducaoForte123!
```

### 6. Firewall

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 7. Auto-renovação de certificados

```bash
echo "0 3 * * * certbot renew --quiet && docker compose restart nginx" | sudo crontab -
```

---

## Estrutura do Projeto

```
MDM_PROJETO/
├── backend/                 # API FastAPI
│   ├── api/                 # Rotas, auth, websockets
│   ├── core/                # Config, database, security
│   ├── models/              # SQLAlchemy models
│   ├── repositories/        # Data access layer
│   ├── schemas/             # Pydantic validation
│   ├── services/            # Business logic
│   ├── main.py              # App entry point
│   └── create_admin.py      # Script criar admin
├── frontend/                # React + Vite
│   ├── src/
│   │   ├── components/      # UI components
│   │   ├── pages/           # Dashboard, Devices, etc.
│   │   ├── contexts/        # Auth context
│   │   ├── services/        # API client (axios)
│   │   └── hooks/           # Custom hooks
│   ├── Dockerfile           # Multi-stage (dev + prod)
│   └── vite.config.ts       # Proxy /api → backend
├── android/                 # DPC Agent (Kotlin)
├── migrations/              # SQL scripts
├── ssl/                     # Certificados TLS
├── docker-compose.yml       # Desenvolvimento
├── docker-compose.prod.yml  # Overrides produção
├── Dockerfile.backend       # Multi-stage backend
├── nginx.conf               # Reverse proxy config
├── .env.example             # Template dev
├── .env.production.example  # Template produção
├── start_docker.ps1         # Helper PowerShell
└── requirements.txt         # Python deps
```

---

## Segurança

- Backend não exposto ao host – apenas Nginx acessa internamente
- Rate limiting no Nginx (API: 10r/s, Auth: 5r/min)
- Security headers (X-Frame-Options, X-Content-Type-Options, etc.)
- JWT com expiração + cookies HTTP-Only
- CORS com origins explícitas (sem wildcard)
- PostgreSQL isolado na rede Docker
- Variáveis obrigatórias – falha se faltarem
- Container backend roda como usuário não-root
- Healthchecks em todos os serviços

---

## Troubleshooting

| Problema | Solução |
|----------|---------|
| "Connection refused" localhost | `docker compose ps` – verificar se estão UP |
| "ERR_NAME_NOT_RESOLVED" no browser | Usar `localhost:3000`, não IP interno Docker |
| Backend 500 no login | `docker compose logs backend` – verificar DATABASE_URL |
| PostgreSQL não inicia | `docker compose down -v && docker compose up -d` |
| Frontend não atualiza | `docker compose restart frontend` ou limpar cache |
| Porta 80 ocupada | Alterar para 8080 no docker-compose.yml |
