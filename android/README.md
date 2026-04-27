<p align="center">
  <h1 align="center">📱 Elion MDM — Android Agent</h1>
  <p align="center">
    <img src="https://img.shields.io/badge/Kotlin-1.9+-7F52FF?style=flat-square&logo=kotlin" />
    <img src="https://img.shields.io/badge/Android-API%2030+-3DDC84?style=flat-square&logo=android" />
    <img src="https://img.shields.io/badge/Android%2015-Compatible-3DDC84?style=flat-square" />
    <img src="https://img.shields.io/badge/Play%20Integrity-Attestation-4285F4?style=flat-square&logo=google" />
  </p>
</p>

> 🔙 [Voltar ao README Principal](../README.md) · ⚡ [Backend API](../backend/README.md) · 🖥️ [Frontend](../frontend/README.md)

---

## Visão Geral

O Android Agent é o componente de campo do Elion MDM. Roda como um Foreground Service persistente (compatível com Android 15), gerenciando o ciclo de vida completo do dispositivo — do enrollment até a execução de comandos remotos, enforcement de políticas e compliance contínuo.

O agent se conecta **diretamente** ao backend FastAPI na porta `8200` — sem Nginx ou proxy reverso intermediário.

---

## Estrutura de Diretórios

```
com.elion.mdm/
├── ElionMDMApp.kt                 # Classe Application
├── AdminReceiver.kt               # DeviceAdminReceiver (Device Owner)
│
├── services/
│   └── MDMForegroundService.kt    # Foreground service — coração do agent
│
├── domain/
│   ├── PolicyManager.kt           # Aplica políticas em ordem determinística
│   ├── CommandHandler.kt          # Executa comandos remotos (LOCK, WIPE, etc.)
│   ├── DevicePolicyHelper.kt      # Wrapper da API Android DPM
│   ├── ComplianceManager.kt       # Motor de compliance local
│   ├── StateReporter.kt           # Reports de saúde para o backend
│   └── usecase/                   # Casos de uso da camada de domínio
│
├── security/
│   ├── AttestationService.kt      # Integração Play Integrity SDK
│   ├── AdminAuthManager.kt        # Segurança de acesso admin local
│   └── KioskSecurityManager.kt    # Anti-escape do modo kiosk
│
├── system/
│   ├── MDMStateMachine.kt         # State machine com 6 estados + backoff
│   ├── KioskManager.kt            # Controlador Lock Task Mode
│   ├── BootReceiver.kt            # Auto-start após boot do dispositivo
│   ├── ApkSilentInstaller.kt      # Instalação silenciosa de APKs
│   ├── EnrollmentStateMachine.kt  # Gerenciamento de fluxo de enrollment
│   ├── OfflineQueue.kt            # Fila offline para operações sem rede
│   └── LocalLogger.kt             # Log local persistente
│
├── data/
│   ├── local/
│   │   └── SecurePreferences.kt   # EncryptedSharedPreferences
│   ├── remote/
│   │   ├── ApiService.kt          # Interface Retrofit (todos os endpoints)
│   │   ├── ApiClient.kt           # OkHttp + Interceptors + URL normalizer
│   │   └── dto/ApiModels.kt       # Data Transfer Objects
│   └── repository/
│       └── DeviceRepository.kt    # Camada de abstração de dados
│
├── presentation/
│   └── MainActivity.kt            # UI de enrollment + status do agent
│
├── launcher/
│   └── KioskLauncherActivity.kt   # Launcher substituto para modo kiosk
│
└── workers/
    └── ApkInstallerWorker.kt      # WorkManager para instalação em background
```

---

## Arquitetura do Agent

### MDMForegroundService — O Coração

O serviço roda permanentemente em foreground (notificação persistente) e orquestra todo o ciclo de vida do MDM. Compatível com **Android 15** usando `FOREGROUND_SERVICE_TYPE_SPECIAL_USE`.

```
┌────────────────────────────────────────────────────────────┐
│                   MDMForegroundService                      │
│                                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │ Check-in │  │ Command  │  │WebSocket │  │  Kiosk    │ │
│  │   Loop   │  │  Poll    │  │ Client   │  │ Watchdog  │ │
│  │  (60s)   │  │  (30s)   │  │(Realtime)│  │  (15s)    │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘ │
│       │             │             │               │        │
│       └─────────────┴─────────────┴───────────────┘        │
│                         │                                   │
│              ┌──────────▼──────────┐                       │
│              │   MDMStateMachine   │                       │
│              │ 6 estados + backoff │                       │
│              └─────────────────────┘                       │
│                                                            │
│  Circuit Breaker: 5 falhas → pausa 5 min (bateria safe)   │
└────────────────────────────────────────────────────────────┘
```

**Loops simultâneos:**
- **Check-in (60s):** Envia heartbeat + telemetria completa (bateria, GPS, apps, armazenamento, foreground app).
- **Command Poll (30s):** Busca comandos pendentes via REST (fallback do WS).
- **WebSocket Client:** Canal em tempo real para comandos push.
- **Kiosk Watchdog (15s):** Verifica se Lock Task Mode está ativo.

---

## Telemetria Enviada

O agent coleta e envia os seguintes dados em cada check-in:

| Dado | Descrição | Permissão Necessária |
|---|---|---|
| `battery_level` | Nível de bateria (%) | Nenhuma |
| `is_charging` | Se está carregando | Nenhuma |
| `device_model` | Fabricante + modelo | Nenhuma |
| `android_version` | Versão do Android | Nenhuma |
| `free_disk_space_mb` | Armazenamento livre (MB) | Nenhuma |
| `installed_apps` | Lista de package names | Nenhuma |
| `foreground_app` | App em primeiro plano | `PACKAGE_USAGE_STATS` |
| `latitude` / `longitude` | Coordenadas GPS | `ACCESS_FINE_LOCATION` |
| `imei` | IMEI do dispositivo | Device Owner |

> **Nota:** O IMEI só é acessível quando o app é Device Owner. Sem Device Owner, o agent reporta todas as outras informações normalmente.

---

## Enrollment via ADB (Manual)

O enrollment atual utiliza instalação manual via ADB:

```bash
# 1. Gere o APK no Android Studio (flavor: dev, build: debug)
./gradlew assembleDevDebug

# 2. Instale no dispositivo conectado
adb install -r app/build/outputs/apk/dev/debug/app-dev-debug.apk

# 3. Abra o app e preencha:
#    - URL do Backend: http://<IP_DO_SERVIDOR>:8200
#    - Bootstrap Secret: (valor do .env do servidor)

# 4. Clique em "Sincronizar"
# → O dispositivo será registrado e aparecerá no dashboard
```

**O que acontece no enrollment:**
1. O agent coleta o modelo do celular e a lista de apps instalados.
2. Envia tudo junto com o Bootstrap Secret para `POST /api/enroll`.
3. O backend gera um token opaco e retorna ao agent.
4. O agent persiste o token em `EncryptedSharedPreferences`.
5. O `MDMForegroundService` inicia automaticamente e começa os loops de check-in.

---

## State Machine — 6 Estados com Anti-Brick

```
              ┌──────────────────────────────────────────────────┐
              │                                                  │
 ┌──────┐    ┌▼──────────┐    ┌────────────┐    ┌───────────┐  │
 │ INIT │───►│REGISTERING│───►│PROVISIONING│───►│ ENFORCING │──┘
 └──────┘    └───────────┘    └────────────┘    └─────┬─────┘
              /enroll OK       Bootstrap OK          │    │
                                                     │    │
                                             Sucesso │    │ Falha
                                                     ▼    ▼
                                             ┌────────┐ ┌───────┐
                                             │OPERATIO│ │ ERROR │
                                             │  NAL   │ │       │
                                             └───┬────┘ └───┬───┘
                                                 │          │
                                                 │  Retry   │
                                           Drift │◄─────────┘
                                         Detected│
                                                 └──► ENFORCING
```

### Proteções Anti-Brick

| Proteção | Mecanismo |
|---|---|
| **Backoff Exponencial** | Delay dobra a cada falha: 5s → 10s → 20s → 40s → 80s |
| **Cooldown** | Após 5 falhas, pausa de 30 minutos (protege CPU/bateria) |
| **Checksum SHA-256** | Estado persistido com checksum, detecta corrupção |
| **Circuit Breaker** | WebSocket para após 5+ falhas consecutivas (freeze de 5min) |

---

## Comandos Suportados

| Comando | Ação | Ciclo de Confirmação |
|---|---|---|
| `LOCK` | Bloqueia a tela imediatamente | ACK → EXECUTED → VERIFIED |
| `WIPE` | Factory reset completo | ACK → EXECUTED → VERIFIED |
| `REBOOT` | Reinicia o dispositivo | ACK → EXECUTED |
| `INSTALL_APP` | Instala APK silenciosamente | ACK → EXECUTED |
| `ENABLE_KIOSK` | Ativa modo kiosk | ACK → EXECUTED |
| `DISABLE_KIOSK` | Desativa modo kiosk | ACK → EXECUTED |
| `DISABLE_CAMERA` | Bloqueia câmera | ACK → EXECUTED |
| `ENABLE_CAMERA` | Libera câmera | ACK → EXECUTED |

> Para a definição do protocolo de comandos no lado do servidor, veja o [README do Backend](../backend/README.md).

---

## Comunicação com o Backend

### Conexão Direta (Sem Proxy)

O agent se conecta **diretamente** ao backend Uvicorn:

```
Agent ──── HTTP/WS ───► http://<IP>:8200/api/...
```

Não há Nginx ou proxy reverso no caminho. A URL é configurável pela tela de enrollment e armazenada em `EncryptedSharedPreferences`.

### Protocolo Duplo (Resiliência)

| Canal | Uso | Fallback |
|---|---|---|
| **WebSocket** | Comandos push em tempo real, presença | → Polling REST |
| **REST Polling** | Busca de comandos pendentes (30s) | Canal primário se WS cair |

### Endpoints Consumidos

| Endpoint | Quando |
|---|---|
| `POST /api/enroll` | Durante enrollment inicial |
| `POST /api/checkin` | Check-in periódico de telemetria (60s) |
| `GET /api/devices/{id}/bootstrap` | Após enrollment (SSOT) |
| `POST /api/devices/{id}/status` | Report de saúde |
| `POST /api/devices/{id}/policy/sync` | Verificação de drift |
| `GET /api/devices/{id}/commands/pending` | Poll de comandos (30s) |
| `POST /api/devices/{id}/commands/{id}/ack` | Confirmação de execução |
| `GET /api/devices/nonce` | Solicitar nonce para atestação |
| `POST /api/devices/attest` | Enviar token de integridade |

---

## Build

### Requisitos

| Ferramenta | Versão Mínima |
|---|---|
| Android Studio | Hedgehog+ |
| JDK | 17+ |
| Gradle | 8.0+ |
| Android SDK | API 30+ (Android 11) |
| Target SDK | API 35 (Android 15) |

### Flavors

| Flavor | `IS_DEV` | Logging | Uso |
|---|---|---|---|
| `dev` | `true` | Verbose (body completo) | Desenvolvimento e testes |
| `prod` | `false` | Nenhum | Produção |

### Compilando

```bash
cd android

# Build debug (desenvolvimento)
./gradlew assembleDevDebug
# APK em: app/build/outputs/apk/dev/debug/

# Build release (produção)
./gradlew assembleProdRelease
# APK em: app/build/outputs/apk/prod/release/
```

---

## Segurança

### Play Integrity (Atestação de Hardware)

1. Agent solicita nonce assinado ao backend.
2. Agent envia nonce para a SDK do Play Integrity.
3. Google retorna token de integridade.
4. Agent envia token ao backend para validação.
5. Backend calcula Trust Score (0–100).

### Armazenamento Seguro

- Todas as credenciais (tokens, segredos) são persistidas via `EncryptedSharedPreferences`.
- Estado da state machine protegido com checksum SHA-256.

### Modo Kiosk

- **Watchdog (15s):** Verifica se Lock Task Mode está ativo.
- **Anti-escape:** Se detectar saída, força re-entrada imediata via `KioskLauncherActivity`.
- **Bloqueios:** Barra de notificações, navegação por botões, barra de status.
