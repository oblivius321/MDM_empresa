# 📱 Elion MDM - Sistema de Gerenciamento de Dispositivos Móveis

![Status](https://img.shields.io/badge/status-active-brightgreen) ![Version](https://img.shields.io/badge/version-1.0.0-blue) ![License](https://img.shields.io/badge/license-MIT-green)

Sistema enterprise-grade de **Mobile Device Management (MDM)** para controle centralizado de dispositivos Android corporativos. Oferece enrollment seguro, aplicação de políticas em tempo real, telemetria completa e auditoria detalhada via painel administrativo web.

## 🎯 Características Principais

- ✅ **Painel Web Moderno** - Dashboard React + Vite com UI responsiva
- ✅ **API RESTful** - Backend FastAPI de alta performance com autenticação JWT
- ✅ **Banco de Dados PostgreSQL** - Armazenamento persistente containerizado
- ✅ **Reverse Proxy Nginx** - API Gateway com TLS/SSL suportado
- ✅ **WebSockets em Tempo Real** - Comunicação bidirecional com dispositivos
- ✅ **DPC Android** - App Kotlin como Device Owner com sincronização automática
- ✅ **Segurança Hardened** - Rate limiting, validação JWT, headers de segurança
- ✅ **Docker Compose Ready** - Deploy completo com um comando
- ✅ **Migrations SQL** - Versionamento de schema com suporte a password reset

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                    INTERNET / USUÁRIO                    │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────▼──────────────┐
        │   Nginx (Reverse Proxy)    │
        │   :80 / :443 (TLS Ready)   │
        └──────────┬─────────┬───────┘
                   │         │
    ┌──────────────▼─┐    ┌─▼─────────────┐
    │    Frontend    │    │   Backend API │
    │  React/Vite   │    │   FastAPI     │
    │  :3000        │    │   :8000       │
    └────────────────┘    └───────┬───────┘
                                  │
                    ┌─────────────▼──────────┐
                    │   PostgreSQL Database  │
                    │   :5432 (privado)      │
                    └────────────────────────┘

════════════════════════════════════════════════════════════

                   ┌──────────────────┐
                   │ Android Client   │
                   │ (DPC)            │
                   │ Retrofit/OkHttp  │
                   └──────┬───────────┘
                          │ HTTPS
                   ┌──────▼──────────┐
                   │ Backend API     │ (Check-ins, Commands)
                   └─────────────────┘
```

### 📦 Stack Tecnológico

| Camada | Tecnologia | Versão | Docker |
|--------|-----------|--------|--------|
| **Frontend** | React + TypeScript + Vite | 18.2 / 5.4 | Node.js 18 |
| **Backend** | Python + FastAPI + SQLAlchemy | 3.12 / 0.104 | Python 3.12 |
| **Database** | PostgreSQL | 15 | postgres:15-alpine |
| **Proxy** | Nginx | Latest | nginx:alpine |
| **Mobile** | Kotlin + Android Enterprise | API 30+ | Gradle 8.x |

---

## 🚀 Quick Start (5 minutos)

### Pré-requisitos
- Docker & Docker Compose instalados
- Git
- Navegador web moderno

### 1️⃣ Clonar o Repositório
```bash
git clone https://github.com/oblivius321/MDM_PROJECT_ELION.git
cd MDM_PROJECT_ELION
```

### 2️⃣ Configurar Variáveis de Ambiente
```bash
# Copiar arquivo de exemplo
cp .env.example .env

# Editar .env com suas credenciais
# Variáveis obrigatórias:
# - DB_USER=postgres
# - DB_PASSWORD=SenhaForte123!
# - SECRET_KEY=sua-chave-secreta-aqui
# - BOOTSTRAP_SECRET=senha-bootstrap-android
# - DEFAULT_ADMIN_PASSWORD=SenhaAdminForte123!
```

### 3️⃣ Iniciar os Containers (Windows PowerShell)
```powershell
# Inicie com build automático
.\start_docker.ps1 -Build

# Ou manualmente via Docker Compose
docker-compose up -d --build
```

### 4️⃣ Criar Usuário Administrador
```bash
docker-compose exec backend python create_admin.py
```

### 5️⃣ Acessar a Aplicação
```
🌐 Painel Web: http://localhost
   Email: admin@empresa.com
   Senha: (conforme DEFAULT_ADMIN_PASSWORD no .env)

🔧 API Backend: http://localhost/api
🗄️ PostgreSQL: localhost:5432
```

---

## 📋 Comandos Úteis do Docker

### Inicializar / Parar
```bash
# Subir com rebuild
docker-compose up -d --build

# Parar containers
docker-compose down

# Parar + remover volumes (limpar dados)
docker-compose down -v
```

### Logs e Debugging
```bash
# Ver logs de todos os containers
docker-compose logs -f

# Ver logs específicos do backend
docker-compose logs -f backend

# Ver status dos containers
docker-compose ps
```

### Executar Comandos no Container
```bash
# Criar usuário admin
docker-compose exec backend python create_admin.py

# Acessar shell do backend
docker-compose exec backend bash

# Acessar psql do banco
docker-compose exec postgres psql -U postgres -d mdm_project
```

---

## 🔐 Segurança

### ✅ Proteções Implementadas

1. **Variáveis Obrigatórias** - Não há fallbacks hardcoded; sistema falha se variáveis críticas faltarem
2. **Autenticação JWT** - Tokens com expiração, usando cookies HTTP-Only no frontend
3. **Rate Limiting** - SlowAPI protege endpoints contra brute force (10 req/s API, 5 req/min auth)
4. **CORS Configurado** - Origins explícitas, sem wildcard em produção
5. **TLS/SSL Pronto** - Certificados self-signed em `/ssl/`, prontos para Let's Encrypt
6. **Headers de Segurança** - HSTS, X-Frame-Options, X-Content-Type-Options
7. **Validação de Input** - Schemas Pydantic com validação rigorosa
8. **Device Token Persistente** - Tokens intransferíveis entre dispositivos

### 🔑 Gerenciamento de Secrets

```bash
# Rotação de chaves secretas quebra todas as sessões ativas
SECRET_KEY = "chave-de-produção-forte-aqui"

# Muda credential de bootstrap para novos enrolls (dispositivos antigos continuam)
BOOTSTRAP_SECRET = "senha-provisória-enrollment"
```

---

## 📱 Cliente Android (DPC)

### Provisionamento Inicial

1. **Factory Reset** o dispositivo
2. **Pulsar QR Code** (gerado no painel Elion) ou usar ADB:
   ```bash
   adb shell dpm set-device-owner com.example.androidmdm/.AdminReceiver
   ```
3. **Inserir Bootstrap Secret** para obter device_token
4. **Aplicação de Políticas** acontece automaticamente

### Funcionalidades Suportadas
- Check-ins periódicos (telemetria)
- Lock/Unlock remoto
- Limpeza (Wipe) de dispositivo
- Instalação de apps (APK)
- Restrições de funcionalidade (camera, USB, etc)
- Monitoramento de compliance

---

## 🗂️ Estrutura do Projeto

```
MDM_PROJECT_ELION/
├── backend/                    # API FastAPI
│   ├── api/
│   │   ├── auth.py            # Endpoints de autenticação
│   │   ├── routes.py          # Rotas da API
│   │   ├── websocket_routes.py # WebSockets tempo real
│   │   └── device_auth.py     # Auth de dispositivos
│   ├── core/
│   │   ├── database.py        # Conexão PostgreSQL async
│   │   ├── security.py        # JWT, hashing
│   │   ├── config.py          # Variáveis globais
│   │   └── limiter.py         # Rate limiting
│   ├── models/                # Modelos SQLAlchemy
│   ├── repositories/          # Data Access Layer
│   ├── schemas/               # Validação Pydantic
│   ├── services/              # Business logic
│   ├── main.py                # App entry point
│   └── create_admin.py        # Script para criar admin
│
├── frontend/                  # React + Vite
│   ├── src/
│   │   ├── components/        # Componentes React
│   │   ├── pages/            # Páginas (Dashboard, Devices, etc)
│   │   ├── contexts/         # Auth context global
│   │   ├── services/         # API client (axios)
│   │   ├── hooks/            # Custom React hooks
│   │   └── App.tsx           # Root component
│   ├── vite.config.ts        # Config Vite
│   └── Dockerfile            # Build Node
│
├── android/                  # App DPC Kotlin
│   ├── app/src/main/java/
│   │   └── com/example/androidmdm/
│   │       ├── MDMService.kt       # Device Owner logic
│   │       ├── AdminReceiver.kt    # Device Admin receiver
│   │       └── network/            # Retrofit + OkHttp
│   └── build.gradle.kts
│
├── migrations/               # SQL scripts versionados
│   ├── 001_initial.sql
│   └── 002_add_password_reset_fields.sql
│
├── docker-compose.yml        # Orquestração de containers
├── Dockerfile.backend        # Build do backend
├── nginx.conf               # Configuração reverse proxy
├── .env.example             # Template de variáveis
└── start_docker.ps1         # Script de inicialização (Windows)
```

---

## 🧪 Testes

```bash
# Rodar testes do backend
docker-compose exec backend pytest

# Rodar testes do frontend
cd frontend && npm test

# Cobertura de testes
docker-compose exec backend pytest --cov=backend
```

---

## 🐛 Troubleshooting

### "Connection refused" ao acessar http://localhost
- Verifique se containers estão rodando: `docker-compose ps`
- Aguarde o healthcheck do PostgreSQL: `docker-compose logs postgres | grep ready`
- Reinicie: `docker-compose restart`

### Backend com erro 404 em /auth/login
- Verifique: `docker-compose logs backend | grep -i error`
- Certifique-se que DATABASE_URL está correto no .env
- Tente: `docker-compose restart backend`

### Frontend não carrega assets do Vite
- Limpe cache do Docker: `docker-compose down -v`
- Rebuild: `docker-compose up -d --build`
- Cache do navegador: Ctrl+Shift+Delete (hard refresh)

### PostgreSQL não inicia
- Resetar volume: `docker-compose down -v && docker-compose up -d`
- Verificar espaço em disco: `df -h`

---

## 📚 Documentação Adicional

- [Guia de Deploy em Produção](./DEPLOYMENT.md) *(em breve)*
- [API Openapi/Swagger](http://localhost/api/docs)
- [Guia de Troubleshooting Android](./android/TROUBLESHOOTING.md)

---

## 🤝 Contribuindo

Para contribuir com melhorias:

1. Fork o repositório
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

---

## 📄 Licença

Este projeto está licenciado sob a MIT License - veja [LICENSE.md](LICENSE.md) para detalhes.

---

## 👤 Autores

**Desenvolvido por:** Equipe MDM Elion  
**Repositório:** https://github.com/oblivius321/MDM_PROJECT_ELION

---

## 📞 Suporte

Para relatar bugs ou solicitar features, abra uma [Issue no GitHub](https://github.com/oblivius321/MDM_PROJECT_ELION/issues).

**Status do Projeto:** ✅ Production Ready (com configuração adequada)
