<p align="center">
  <h1 align="center">📱 Elion MDM — Android Agent</h1>
  <p align="center">
    <img src="https://img.shields.io/badge/Kotlin-1.9+-7F52FF?style=flat-square&logo=kotlin" />
    <img src="https://img.shields.io/badge/Android-API%2028+-3DDC84?style=flat-square&logo=android" />
    <img src="https://img.shields.io/badge/Device%20Owner-DPC-FF6F00?style=flat-square" />
    <img src="https://img.shields.io/badge/Play%20Integrity-Attestation-4285F4?style=flat-square&logo=google" />
  </p>
</p>

> 🔙 [Voltar ao README Principal](../README.md) · ⚡ [Backend API](../backend/README.md) · 🖥️ [Frontend](../frontend/README.md)

---

## Visão Geral

O Android Agent é o componente de campo do Elion MDM. Roda como **Device Owner (DPC)** com um Foreground Service persistente, gerenciando o ciclo de vida completo do dispositivo — do enrollment zero-touch até a execução de comandos remotos, enforcement de políticas e compliance contínuo.

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
│   │   ├── ApiClient.kt           # OkHttp + Interceptors
│   │   └── dto/ApiModels.kt       # Data Transfer Objects
│   └── repository/
│       └── DeviceRepository.kt    # Camada de abstração de dados
│
├── presentation/
│   └── MainActivity.kt            # UI de enrollment (scanner QR Code)
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

O serviço roda permanentemente em foreground (notificação persistente no Android 8+) e orquestra todo o ciclo de vida do MDM:

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
- **Check-in (60s):** Envia heartbeat + telemetria para o backend.
- **Command Poll (30s):** Busca comandos pendentes via REST (fallback do WS).
- **WebSocket Client:** Canal em tempo real para comandos push.
- **Kiosk Watchdog (15s):** Verifica se Lock Task Mode está ativo.

---

## State Machine — 6 Estados com Anti-Brick

```
              ┌──────────────────────────────────────────────────┐
              │                                                  │
 ┌──────┐    ┌▼──────────┐    ┌────────────┐    ┌───────────┐  │
 │ INIT │───►│REGISTERING│───►│PROVISIONING│───►│ ENFORCING │──┘
 └──────┘    └───────────┘    └────────────┘    └─────┬─────┘
   QR Scan      /enroll OK      Bootstrap OK        │    │
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

| Estado | Descrição | Transição |
|---|---|---|
| `INIT` | Dispositivo virgem, aguarda enrollment | → REGISTERING (QR scan) |
| `REGISTERING` | Handshake de identidade em andamento | → PROVISIONING (enroll OK) |
| `PROVISIONING` | Baixando Bootstrap SSOT | → ENFORCING (download OK) |
| `ENFORCING` | Aplicando políticas deterministicamente | → OPERATIONAL / ERROR |
| `OPERATIONAL` | Dispositivo gerenciado e compliant | → ENFORCING (drift detectado) |
| `ERROR` | Falha com backoff exponencial | → ENFORCING (retry) / Cooldown 30min |

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
| `UNLOCK` | Remove lock de tela | ACK → EXECUTED |
| `SET_POLICY` | Atualiza políticas | ACK → EXECUTED |
| `INSTALL_APP` | Instala APK silenciosamente | ACK → EXECUTED |
| `UNINSTALL_APP` | Remove app | ACK → EXECUTED |
| `ENABLE_KIOSK` | Ativa modo kiosk | ACK → EXECUTED |
| `DISABLE_KIOSK` | Desativa modo kiosk | ACK → EXECUTED |

> Para a definição do protocolo de comandos no lado do servidor, veja o [README do Backend](../backend/README.md).

---

## Segurança

### Play Integrity (Atestação de Hardware)

O agent integra a **Play Integrity API** do Google para provar que está rodando em um dispositivo Android legítimo:

1. Agent solicita nonce assinado ao backend.
2. Agent envia nonce para a SDK do Play Integrity.
3. Google retorna token de integridade.
4. Agent envia token ao backend para validação.
5. Backend calcula Trust Score (0–100).

### Modo Kiosk

- **Watchdog (15s):** Verifica se Lock Task Mode está ativo.
- **Anti-escape:** Se detectar saída, força re-entrada imediata via `KioskLauncherActivity`.
- **Bloqueios:** Barra de notificações, navegação por botões, barra de status.

### Armazenamento Seguro

- Todas as credenciais (tokens, segredos) são persistidas via `EncryptedSharedPreferences`.
- Estado da state machine protegido com checksum SHA-256.

---

## Build e Provisionamento

### Requisitos

| Ferramenta | Versão Mínima |
|---|---|
| Android Studio | Hedgehog+ |
| JDK | 17+ |
| Gradle | 8.0+ |
| Android SDK | API 28+ (Android 9) |

### Build

```bash
cd android

# Configurar local.properties com sdk.dir
# sdk.dir=C:\\Users\\<user>\\AppData\\Local\\Android\\Sdk

./gradlew assembleDebug
# APK em: app/build/outputs/apk/debug/
```

### Provisionamento como Device Owner

1. **Factory reset** do dispositivo Android.
2. Na tela de boas-vindas, toque 6x no ecrã para ativar o leitor QR.
3. Escaneie o QR Code gerado pelo dashboard do Elion MDM.
4. O dispositivo será provisionado automaticamente como Device Owner.

> O QR Code contém: `profile_id`, `bootstrap_secret`, `api_url`.

---

## Comunicação com o Backend

### Protocolo Duplo (Resiliência)

| Canal | Uso | Fallback |
|---|---|---|
| **WebSocket** | Comandos push em tempo real, presença | → Polling REST |
| **REST Polling** | Busca de comandos pendentes (30s) | Canal primário se WS cair |

### Endpoints Consumidos

| Endpoint | Quando |
|---|---|
| `POST /api/enroll` | Durante enrollment inicial |
| `GET /api/devices/{id}/bootstrap` | Após enrollment (SSOT) |
| `POST /api/devices/{id}/status` | Check-in periódico (60s) |
| `POST /api/devices/{id}/policy/sync` | Verificação de drift |
| `GET /api/devices/{id}/commands/pending` | Poll de comandos (30s) |
| `POST /api/devices/{id}/commands/{id}/ack` | Confirmação de execução |
| `GET /api/devices/nonce` | Solicitar nonce para atestação |
| `POST /api/devices/attest` | Enviar token de integridade |
