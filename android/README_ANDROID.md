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

## Compilar

Abra o projeto no Android Studio. Requer **JDK 17+**.
