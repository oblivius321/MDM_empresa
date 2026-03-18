# Elion MDM — Android DPC Agent

Agente Device Owner (DPC) para o sistema Elion MDM.  
Kotlin · Android 11+ (API 30) · Clean Architecture

---

## Estrutura do Projeto

```
app/src/main/
├── java/com/elion/mdm/
│   ├── AdminReceiver.kt                  ← DeviceAdminReceiver (ponto de entrada DO)
│   ├── BootReceiver.kt                   ← Reinicia serviço após reboot
│   ├── ElionMDMApp.kt                    ← Application class
│   │
│   ├── data/
│   │   ├── local/
│   │   │   └── SecurePreferences.kt      ← EncryptedSharedPreferences (AES-256)
│   │   ├── remote/
│   │   │   ├── ApiService.kt             ← Interface Retrofit (endpoints)
│   │   │   ├── ApiClient.kt              ← OkHttp + AuthInterceptor + singleton
│   │   │   └── dto/
│   │   │       └── ApiModels.kt          ← DTOs request/response
│   │   └── repository/
│   │       └── DeviceRepository.kt       ← Acesso a dados (remote + local)
│   │
│   ├── domain/
│   │   ├── DevicePolicyHelper.kt         ← Wrapper DevicePolicyManager
│   │   ├── CommandHandler.kt             ← Executa comandos remotos
│   │   └── usecase/
│   │       └── UseCases.kt               ← EnrollDeviceUseCase, GetDeviceStatusUseCase
│   │
│   ├── services/
│   │   ├── MDMForegroundService.kt       ← Check-in + polling + WebSocket
│   │   └── ApkInstallerService.kt        ← Download + instalação silenciosa APK
│   │
│   ├── workers/
│   │   └── MDMWorker.kt                  ← WorkManager (redundância ao Foreground)
│   │
│   └── presentation/
│       ├── MainActivity.kt               ← Tela enrollment / status
│       └── MainViewModel.kt              ← ViewModel com StateFlow
│
├── res/
│   ├── layout/activity_main.xml
│   ├── xml/
│   │   ├── device_admin_policies.xml     ← Políticas declaradas ao sistema
│   │   └── network_security_config.xml   ← Força HTTPS em produção
│   └── values/
│       ├── strings.xml
│       └── themes.xml
│
└── AndroidManifest.xml
```

---

## Como Device Owner Funciona

### O que é Device Owner (DO)?

Device Owner é o **nível máximo de controle** no Android Enterprise.
Um app pode ser DO em apenas **um dispositivo de cada vez**, e
essa ativação normalmente exige que o dispositivo esteja em **factory reset**.

### Por que algumas features só funcionam com DO?

| Feature                     | Device Admin | Device Owner |
|-----------------------------|:------------:|:------------:|
| `lockNow()`                 | ✅            | ✅            |
| `wipeData()` (flags extras) | ❌            | ✅            |
| `setLockTaskPackages()`     | ❌            | ✅ (Kiosk)   |
| `setStatusBarDisabled()`    | ❌            | ✅            |
| `setCameraDisabled()`       | ✅ (escopo limitado) | ✅ (global) |
| `reboot()`                  | ❌            | ✅            |
| `addUserRestriction()`      | ❌            | ✅            |
| Instalar APK silencioso     | ❌            | ✅            |

O Android usa o modelo de **privilege escalation** para proteger o usuário.
Um Device Admin pode apenas sugerir políticas; um Device Owner **impõe** políticas
sem possibilidade de bypass pelo usuário.

---

## Setup Inicial

### 1. Pré-requisitos

- Android Studio Hedgehog (2023.1.1) ou superior
- JDK 17
- Dispositivo Android 11+ **em factory reset** (para ativar DO)
- Depuração USB habilitada

### 2. Clonar e abrir

```bash
git clone <repo-url>
# Abrir a pasta elion-mdm no Android Studio
```

### 3. Build

```bash
./gradlew assembleDebug
# APK gerado em: app/build/outputs/apk/debug/app-debug.apk
```

### 4. Instalar no dispositivo

```bash
adb install app/build/outputs/apk/debug/app-debug.apk
```

---

## Ativar como Device Owner (ADB)

> ⚠️ O dispositivo deve estar **sem contas Google** e em estado de **factory reset**.
> Se houver contas, execute: `Configurações → Contas → Remover todas`

```bash
# Verificar se o dispositivo está conectado
adb devices

# Ativar como Device Owner
adb shell dpm set-device-owner com.elion.mdm/.AdminReceiver

# Resposta esperada:
# Success: Device owner set to package com.elion.mdm
```

### Verificar se é Device Owner

```bash
adb shell dpm list-owners
# Deve mostrar: com.elion.mdm/.AdminReceiver
```

### Remover Device Owner (para testes)

```bash
# Opção 1: via ADB (apenas debug)
adb shell dpm remove-active-admin com.elion.mdm/.AdminReceiver

# Opção 2: factory reset do dispositivo
adb shell am broadcast -a android.intent.action.FACTORY_RESET
```

---

## Fluxo de Enrollment

```
Técnico abre o app
       │
       ▼
Preenche Backend URL + Bootstrap Secret
       │
       ▼
POST /api/device/enroll
  { bootstrap_secret, device_model, android_version, serial }
       │
       ▼ (backend valida o secret)
Recebe { device_id, device_token }
       │
       ▼
Salva token no EncryptedSharedPreferences (AES-256)
       │
       ▼
Inicia MDMForegroundService
       │
       ├── Loop check-in (60s padrão)
       ├── Loop command poll (30s fallback)
       └── WebSocket conectado (tempo real)
```

---

## Comandos Suportados

| Tipo                 | Ação                                        | Requer DO |
|----------------------|---------------------------------------------|:---------:|
| `LOCK`               | Bloqueia a tela imediatamente               | ❌         |
| `WIPE`               | Factory reset (irreversível)                | ✅         |
| `KIOSK`              | Ativa Kiosk Mode para um pacote             | ✅         |
| `KIOSK_DISABLE`      | Desativa Kiosk Mode                         | ✅         |
| `DISABLE_CAMERA`     | Desativa câmera globalmente                 | ✅         |
| `ENABLE_CAMERA`      | Reativa câmera                              | ✅         |
| `DISABLE_STATUS_BAR` | Oculta status bar e quick settings          | ✅         |
| `ENABLE_STATUS_BAR`  | Reativa status bar                          | ✅         |
| `INSTALL_APK`        | Baixa e instala APK silenciosamente         | ✅         |
| `REBOOT`             | Reinicia o dispositivo                      | ✅         |
| `SYNC_POLICY`        | Busca e aplica políticas atualizadas        | -         |

### Exemplo de payload INSTALL_APK (backend → dispositivo):

```json
{
  "id": 42,
  "type": "INSTALL_APK",
  "payload": {
    "url": "https://cdn.suaempresa.com/apps/meuapp-v2.0.apk"
  }
}
```

### Exemplo de payload KIOSK:

```json
{
  "id": 43,
  "type": "KIOSK",
  "payload": {
    "package": "com.suaempresa.kioskapp"
  }
}
```

---

## Testar via ADB (sem backend)

```bash
# Simular LOCK
adb shell am broadcast -a com.elion.mdm.TEST_LOCK

# Ver logs em tempo real
adb logcat -s ElionMDMService ElionCommandHandler ElionDPM ElionAdminReceiver

# Ver se o serviço está rodando
adb shell dumpsys activity services com.elion.mdm
```

---

## Variáveis de Configuração

| Variável                | Onde configurar        | Padrão                         |
|-------------------------|------------------------|--------------------------------|
| Backend URL             | UI de enrollment       | `https://mdm.suaempresa.com`   |
| Bootstrap Secret        | UI de enrollment       | —                              |
| Check-in interval       | Retornado pelo backend | 60 segundos                    |
| WorkManager interval    | `MDMWorker.kt`         | 15 minutos (mínimo do sistema) |

---

## Dependências Principais

| Biblioteca                    | Versão   | Uso                              |
|-------------------------------|----------|----------------------------------|
| `androidx.security:crypto`    | 1.1.0-α6 | EncryptedSharedPreferences       |
| `retrofit2`                   | 2.11.0   | Cliente HTTP tipado              |
| `okhttp3`                     | 4.12.0   | HTTP + WebSocket + Interceptors  |
| `kotlinx.coroutines`          | 1.8.1    | Async/await no Android           |
| `androidx.work:work-runtime`  | 2.9.x    | Background periódico robusto     |
| `androidx.lifecycle:viewmodel`| 2.8.x    | ViewModel + StateFlow            |

---

## Segurança

- **Token armazenado** em `EncryptedSharedPreferences` (AES-256-GCM)
- **HTTPS obrigatório** em produção via `network_security_config.xml`
- **Backend não exposto** — apenas via Nginx reverse proxy
- **ProGuard ativo** em builds release (R8 + minificação)
- **Sem logs sensíveis** em builds release (logging interceptor desativado)
