# 🔐 Configuração de Ambiente (.env)

Guia prático sobre as variáveis de ambiente do projeto.

---

## 📋 Arquivos .env

| Arquivo | Localização | Propósito | Quando Usar |
|---------|------------|----------|-----------|
| `.env.development` | Root | Dev local | `npm run dev`, `python main.py` |
| `.env.production` | Root | Produção | Deploy com Docker, HTTPS |
| `frontend/.env` | frontend/ | Vite config | Já configurado, customize se necessário |
| `backend/.env.example` | backend/ | Template | Copie para `backend/.env` |

---

## 🔧 Variáveis Essenciais

### DATABASE
```env
DATABASE_URL=postgresql+asyncpg://USER:PASS@HOST:5432/DB_NAME
```
**Development:** `localhost:5432/mdm_project`  
**Production:** `db-prod:5432/mdm_project` (via docker)

### SECURITY
```env
SECRET_KEY=seu-secret-key-aleatorio-32-caracteres
DEBUG=True/False
ENVIRONMENT=development/production
```

### API URLS
```env
API_URL=http://localhost:8000           # Backend URL
FRONTEND_URL=http://localhost:5173      # Frontend URL
VITE_API_URL=http://localhost:8000/api  # Frontend → Backend
ANDROID_API_BASE_URL=http://localhost:8000/api  # Device → Backend
```

### CORS
```env
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

### LOGGING
```env
LOG_LEVEL=DEBUG      # DEBUG, INFO, WARNING, ERROR
```

---

## 🚀 Setup por Tipo

### 1. Development (Local)

**Arquivo:** `.env.development`

```bash
# Usar como base
cp .env.development /tmp/.env.current

# Backend
cd backend/
cp .env.example .env
cat .env  # Verificar valores já corretos para dev

# Frontend
cd frontend/
cat .env  # Já tem VITE_API_URL=http://localhost:8000/api

# Iniciar
python backend/main.py  # Terminal 1
npm run dev --prefix frontend  # Terminal 2
```

### 2. Staging (Pré-produção)

**Arquivo:** `.env.production` (customize)

```env
DATABASE_URL=postgresql+asyncpg://user:pass@staging-db:5432/mdm_project
API_URL=https://staging.seudominio.com
VITE_API_URL=https://staging.seudominio.com/api
SSL_CERT_PATH=/etc/nginx/ssl/staging.crt
SSL_KEY_PATH=/etc/nginx/ssl/staging.key
```

### 3. Production (Servidor)

**Arquivo:** `.env.production` (final)

```env
DATABASE_URL=postgresql+asyncpg://user:STRONG_PASS@db-prod:5432/mdm_project
SECRET_KEY=GENERATE_WITH: python -c "import secrets; print(secrets.token_urlsafe(32))"
API_URL=https://api.seudominio.com
VITE_API_URL=https://api.seudominio.com/api
ANDROID_API_BASE_URL=https://api.seudominio.com/api
ALLOWED_ORIGINS=https://mdm.seudominio.com,https://admin.seudominio.com
SSL_CERT_PATH=/etc/nginx/ssl/cert.pem
SSL_KEY_PATH=/etc/nginx/ssl/key.pem
DEBUG=False
ENVIRONMENT=production
```

---

## 🔒 Segurança

### ⚠️ NÃO FAÇA:
```bash
❌ git add .env              # Nunca commitar credenciais
❌ git add .env.production
❌ git add backend/.env
❌ echo "SECRET_KEY=abc123" # Não hardcoded
```

### ✅ FAÇA:
```bash
✅ git add .env.development     # OK (locais)
✅ git add backend/.env.example # OK (template)
✅ .env* no .gitignore         # Arquivo já tem isso
✅ Usar AWS Secrets Manager para prod
```

### Gerar Secrets Seguros:
```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Linux/Mac
openssl rand -base64 24

# PowerShell
[System.Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(24))
```

---

## 📊 Checklist por Ambiente

### Local Development
```
[ ] .env.development preenchido
[ ] frontend/.env tem VITE_API_URL
[ ] PostgreSQL rodando em localhost
[ ] Backend inicia em :8000
[ ] Frontend inicia em :5173
```

### Before Production Deploy
```
[ ] .env.production preenchido com domínio real
[ ] SECRET_KEY gerado aleatoriamente
[ ] DATABASE_URL aponta para servidor prod
[ ] ALLOWED_ORIGINS tem domínio correto
[ ] SSL_CERT_PATH e SSL_KEY_PATH corretos
[ ] DEBUG=False
[ ] Testado em staging primeiro
```

---

## 🆘 Problemas Comuns

### "KeyError: DATABASE_URL"
```bash
# Verificar se .env está sendo carregado
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('DATABASE_URL'))"
```

### "CORS policy blocked"
```bash
# Verificar ALLOWED_ORIGINS no .env
echo $ALLOWED_ORIGINS

# Garantir que inclui seu domínio/localhost
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8000
```

### "API call 500 error"
```bash
# Verificar logs do backend
# Comum: DATABASE_URL inválida ou secret key diferente entre requisições
tail -f backend.log
```

### Frontend não conecta API
```bash
# Verificar VITE_API_URL
cat frontend/.env

# Se mudou deve reconstruir
npm run build --prefix frontend
```

---

## 📝 Exemplo Completo: Development

**File:** `.env.development`

```env
# ===== BANCO DE DADOS =====
DATABASE_URL=postgresql+asyncpg://postgres:Sherlock314@localhost:5432/mdm_project

# ===== SEGURANÇA =====
SECRET_KEY=dev-secret-key-change-in-production

# ===== MODO =====
DEBUG=True
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# ===== API =====
API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173

# ===== URLS INTERNAS =====
VITE_API_URL=http://localhost:8000/api
ANDROID_API_BASE_URL=http://localhost:8000/api

# ===== CORS =====
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8000

# ===== DISPOSITIVOS =====
DEVICE_CHECKIN_TIMEOUT=300
```

---

## 🔄 Carregamento de .env

### Backend (Python)

```python
# main.py automaticamente carrega .env via python-dotenv
from dotenv import load_dotenv
import os

load_dotenv()
db_url = os.getenv("DATABASE_URL")
debug = os.getenv("DEBUG") == "True"
```

### Frontend (Vite)

```typescript
// Prefixo VITE_ obrigatório
const apiUrl = import.meta.env.VITE_API_URL
const apiTimeout = import.meta.env.VITE_API_TIMEOUT

// Em tempo de build, variáveis são substituídas
```

### Android (gradle.properties)

```properties
// Use em BuildConfig
API_SERVER_URL=http://localhost:8000
```

---

## ✅ Resumo Rápido

```bash
# 1. Development
cp .env.development .env  # ou customize
python main.py

# 2. Production
cp .env.production .env   # customize com domínio real
docker-compose up -d

# 3. Never commit
git add .gitignore        # Já ignora *.env
git status               # Verificar nenhum .env foi incluído
```

---

**Próximos passos:**
1. Preencha os valores em `.env.development`
2. Siga [SETUP.md](./SETUP.md) para configurar banco e iniciar
3. Consulte [ESSENTIALS.md](./ESSENTIALS.md) para próximos passos

**Referência:** [README.md](./README.md) | [SETUP.md](./SETUP.md)
