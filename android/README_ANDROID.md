# 🤖 Elion MDM — Android DPC Agent

Agente Android Enterprise com Device Owner (DPC) e Kiosk Launcher endurecido.

## Arquitetura

```
android/
├── 🏠 Launcher
│   ├── KioskLauncherActivity.kt    # HOME app com Lock Task Mode
│   ├── AllowedAppAdapter.kt        # Grid de apps permitidos
│   └── activity_kiosk_launcher.xml # Layout do launcher
│
├── 🔐 Admin
│   ├── AdminLoginActivity.kt       # Login seguro (brute-force protect)
│   ├── AdminPanelActivity.kt       # Painel de controle (PT-BR)
│   ├── activity_admin_login.xml    # Layout do login
│   └── activity_admin_panel.xml    # Layout do painel
│
├── 🛡️ Security
│   ├── AdminAuthManager.kt         # Auth backend + fallback local
│   └── KioskSecurityManager.kt     # Watchdog anti-tampering (15s)
│
├── ⚙️ System
│   ├── KioskManager.kt             # Orquestrador kiosk
│   ├── BootReceiver.kt             # Auto-start no boot
│   ├── AdminReceiver.kt            # Device Owner receiver
│   └── DevicePolicyHelper.kt       # Abstração DPM
│
├── 📡 Network
│   ├── ApiClient.kt                # Retrofit + interceptors
│   ├── ApiService.kt               # Endpoints da API
│   └── ApiModels.kt                # DTOs
│
├── 💾 Data
│   └── SecurePreferences.kt        # AES-256-GCM encrypted storage
│
├── 🔄 Services
│   ├── MDMForegroundService.kt     # Check-in + WebSocket + polling
│   └── CommandHandler.kt           # Executor de comandos remotos
│
└── AndroidManifest.xml             # HOME filter + permissions
```

## Ativar Device Owner

```bash
adb shell dpm set-device-owner com.elion.mdm/.AdminReceiver
```

Para o APK dev, o pacote instalado e o Device Owner mudam para `com.elion.mdm.dev`.

## Enrollment via ADB USB

Use este fluxo enquanto o QR Code/AMAPI estiver bloqueado por cota. O comando `dpm set-device-owner` exige aparelho recem-resetado, sem conta Google configurada e sem outro Device Owner.

```bash
adb install -r app/build/outputs/apk/dev/debug/app-dev-debug.apk
adb shell dpm set-device-owner com.elion.mdm.dev/.AdminReceiver
adb reverse tcp:8200 tcp:8200
adb shell am start -n com.elion.mdm.dev/.presentation.MainActivity --es api_url http://127.0.0.1:8200 --es bootstrap_token SEU_TOKEN --es profile_id SEU_PROFILE_ID
```

Se nao usar `adb reverse`, troque `api_url` pelo IP acessivel pelo Android, por exemplo `http://192.168.25.227:8200`.

## Compilar

Abra o projeto no Android Studio. Requer **JDK 17+**.
