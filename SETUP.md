# 🚀 Setup Inicial - Elion MDM

Siga estes passos para configurar o projeto em sua máquina.

---

## 1️⃣ Clonar & Instalar Dependências

```bash
# Clonar repo
git clone <repo-url>
cd MDM_PROJETO

# Backend
cd backend/
pip install -r requirements.txt

# Frontend
cd ../frontend/
npm install

# Android - abrir em Android Studio
# File → Open → android/
```

---

## 2️⃣ Configurar Variáveis de Ambiente

### Backend (Development)

Copie e customize `backend/.env.example`:

```bash
cd backend/
cp .env.example .env  # ou manualmente editar
```

**Valores necessários:**
```env
DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@localhost:5432/mdm_project
SECRET_KEY=seu-secret-aleatorio-aqui
DEBUG=True
ENVIRONMENT=development
API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173
ANDROID_API_BASE_URL=http://localhost:8000/api
```

### Frontend (Development)

Use o arquivo criado:

```bash
cd frontend/
cat .env  # já configurado com VITE_API_URL
```

**Customize se necessário:**
```env
VITE_API_URL=http://localhost:8000/api
VITE_API_TIMEOUT=30000
VITE_DEBUG=true
```

---

## 3️⃣ Iniciar Banco de Dados

```bash
# PostgreSQL deve estar rodando
psql -U postgres -c "CREATE DATABASE mdm_project;"

# Aplicar migrations
cd ..
python pg_migrate.py upgrade
```

---

## 4️⃣ Iniciar Serviços

**Terminal 1 - Backend:**
```bash
cd backend/
python main.py
# Disponível em http://localhost:8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend/
npm run dev
# Disponível em http://localhost:5173
```

**Terminal 3 - Android (opcional):**
```bash
cd android/
./gradlew assembleDebug
# APK em app/build/outputs/apk/debug/app-debug.apk
```

---

## 5️⃣ Testar Conectividade

```bash
# API Health
curl http://localhost:8000/health

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password"}'

# Frontend deve carregar em http://localhost:5173
```

---

## 📱 Provisionar Device Android

### Pré-requisitos
- Device/Emulator com Android 10+
- USB cable se for device físico
- ADB configurado

### Passos

```bash
# 1. Instalar APK
adb install -r android/app/build/outputs/apk/debug/app-debug.apk

# 2. Set como Device Owner
adb shell dpm set-device-owner com.example.androidmdm/.ElionAdminReceiver

# 3. Verificar
adb shell dpm get-device-owner
# Output: com.example.androidmdm/.ElionAdminReceiver

# 4. Conceder permissões
adb shell pm grant com.example.androidmdm android.permission.ACCESS_FINE_LOCATION
adb shell pm grant com.example.androidmdm android.permission.SYSTEM_ALERT_WINDOW
adb shell pm grant com.example.androidmdm android.permission.PACKAGE_USAGE_STATS

# 5. Verificar logs
adb logcat | grep ElionMDM
```

**Se tiver erro:**
- Veja [android/TROUBLESHOOTING_GUIDE.md](./android/TROUBLESHOOTING_GUIDE.md)

---

## 🎯 Variáveis por Ambiente

### Development (.env.development)
```env
DATABASE_URL=postgresql+asyncpg://...@localhost:5432/mdm_project
DEBUG=True
ENVIRONMENT=development
VITE_API_URL=http://localhost:8000/api
```

### Production (.env.production)
```env
DATABASE_URL=postgresql+asyncpg://...@db-prod:5432/mdm_project
DEBUG=False
ENVIRONMENT=production
VITE_API_URL=https://api.seudominio.com/api
SSL_CERT_PATH=/etc/nginx/ssl/cert.pem
```

---

## ✅ Checklist Final

- [ ] PostgreSQL rodando
- [ ] Backend startup sem erros
- [ ] Frontend carrega em localhost:5173
- [ ] API responde com /health
- [ ] Login funciona
- [ ] Android APK instalado (se testando device)

---

## 🆘 Problemas Comuns

| Erro | Solução |
|------|---------|
| `DATABASE_URL` não encontrado | Copie `.env.example` para `.env` |
| Backend não conecta DB | Verifique `psql` rodando e PASSWORD correto |
| Frontend não conecta API | Verifique `VITE_API_URL` e backend rodando |
| Device owner "not an admin" | Execute `adb shell dpm set-device-owner` |

Veja [android/TROUBLESHOOTING_GUIDE.md](./android/TROUBLESHOOTING_GUIDE.md) para mais detalhes.

---

**Próximos passos após setup:**
1. Fazer login no dashboard
2. Registrar primeiro device
3. Enviar comando remoto para testar
4. Consultar logs

Use [ESSENTIALS.md](./ESSENTIALS.md) para navegar documentação rápida.
