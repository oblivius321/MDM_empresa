# 📌 ESSENTIALS - Arquivos Críticos do Projeto

## 🔴 Obrigatório Ler PRIMEIRO

1. **[README.md](./README.md)** - Visão geral e quick start (5 min)
2. **[android/README_MDM.md](./android/README_MDM.md)** - Build, deploy, testes Android (15 min)
3. **[android/PROVISIONING_GUIDE.md](./android/PROVISIONING_GUIDE.md)** - Setup Device Owner (10 min)

---

## 🟡 Essencial Para Deploy

- **[.env.development](./.env.development)** - Variáveis locais
- **[.env.production](./.env.production)** - Variáveis produção
- **[docker-compose.yml](./docker-compose.yml)** - Containers
- **[backend/.env.example](./backend/.env.example)** - Exemplo backend

---

## 🟢 Referência (Se Necessário)

- **[android/TROUBLESHOOTING_GUIDE.md](./android/TROUBLESHOOTING_GUIDE.md)** - Troubleshoot erros
- **[docs/QA_TESTING_PLAN.md](./docs/QA_TESTING_PLAN.md)** - Plano de testes
- **[CHANGELOG.md](./CHANGELOG.md)** - Histórico de mudanças

---

## ✅ Variáveis de Ambiente Configuradas

```
✅ .env.development     - Desenvolvimento local
✅ .env.production      - Produção com domínio/HTTPS
✅ frontend/.env         - Frontend React (VITE_API_URL)
✅ backend/.env.example - Backend Python (exemplo)
```

---

## 🗂️ Estrutura Simplificada

```
MDM_PROJETO/
├── .env.development         ← LOCAL
├── .env.production          ← PROD
├── README.md                ← START HERE
├── docker-compose.yml       ← DEPLOY
└── android/
    ├── README_MDM.md        ← BUILD & DEPLOY
    ├── PROVISIONING_GUIDE.md ← SETUP DEVICE
    └── TROUBLESHOOTING_GUIDE.md ← DEBUG
├── frontend/
    ├── .env                 ← VITE CONFIG
    └── src/
├── backend/
    ├── .env.example         ← REFERENCE
    └── main.py
└── docs/
    └── QA_TESTING_PLAN.md   ← TESTING
```

---

## 🚀 Quick Commands

```bash
# Desenvolvimento
python main.py              # Backend (8000)
npm run dev                 # Frontend (5173)
./gradlew assembleDebug     # Android APK

# Provisioning Android
adb install app-debug.apk
adb shell dpm set-device-owner com.example.androidmdm/.ElionAdminReceiver

# Produção
docker-compose up -d        # Deploy completo
```

---

**Versão:** 1.0.0  
**Últimas Mudanças:** Removida documentação não-essencial, organizado .env
