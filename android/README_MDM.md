# Elion MDM - Android DPC Implementation

Complete Device Policy Controller (DPC) implementation for Android 10+ with advanced MDM features.

## 🎯 Features Implemented

### ✅ Core MDM Functionality
- **Device Owner Provisioning** - ADB and QR code methods
- **Boot Auto-Start** - MDMService starts automatically on device restart
- **Periodic Check-ins** - WorkManager runs every 15 minutes with exponential backoff
- **Command Execution** - Real-time policy enforcement (reboot, wipe, lock, camera, kiosk)
- **Telemetry Collection** - Battery, disk, location, app inventory, activity tracking

### ✅ Advanced Features
- **FusedLocationProvider** - High-accuracy location with suspend/resume
- **UsageStatsManager** - App usage monitoring and foreground app detection
- **ActivityMonitor** - Daily app usage statistics
- **PolicyManager** - Device policy enforcement with security checks
- **NotificationCompat** - Foreground service with persistent notification
- **Exponential Backoff** - Retry logic for failed check-ins

### ✅ Security & Optimization
- **Foreground Service** - Android 8.0+ compliance for background execution
- **SharedPreferences** - Encrypted device ID storage
- **Coroutines** - Non-blocking async operations
- **Error Handling** - Comprehensive logging and retry strategies
- **Permission Validation** - Runtime checks for admin privileges

---

## 🏗️ Project Structure

```
android/
├── app/
│   ├── src/main/
│   │   ├── java/com/example/androidmdm/
│   │   │   ├── MainActivity.kt                    # Permission setup UI
│   │   │   ├── ElionAdminReceiver.kt              # Device admin receiver
│   │   │   ├── BootReceiver.kt                    # Boot completion handler
│   │   │   ├── MDMService.kt                      # Main MDM service
│   │   │   ├── CheckInWorker.kt                   # WorkManager check-in task
│   │   │   ├── PolicyManager.kt                   # Policy enforcement
│   │   │   ├── InventoryManager.kt                # Hardware/app inventory
│   │   │   ├── ActivityMonitor.kt                 # App usage tracking
│   │   │   ├── LocationProvider.kt                # Location acquisition
│   │   │   ├── OverlayManager.kt                  # Display control
│   │   │   ├── KioskLauncher.kt                   # Kiosk mode manager
│   │   │   ├── ScreenCaptureManager.kt            # Screen management
│   │   │   ├── ElionFirebaseMessagingService.kt   # FCM integration (ready)
│   │   │   └── network/
│   │   │       ├── ElionAPI.kt                    # Retrofit API interface
│   │   │       ├── RetrofitClient.kt              # HTTP client setup
│   │   │       └── Payloads.kt                    # Data classes
│   │   ├── AndroidManifest.xml                    # App manifest
│   │   └── res/
│   │       ├── values/                            # Strings, colors, styles
│   │       ├── layout/                            # Legacy XML layouts (if any)
│   │       └── xml/
│   │           ├── device_admin_policies.xml      # DPC policies declaration
│   │           └── data_extraction_rules.xml      # Backup rules
│   ├── build.gradle.kts                           # App dependencies
│   └── proguard-rules.pro                         # ProGuard obfuscation
├── build.gradle.kts                               # Project-level config
├── gradle/libs.versions.toml                      # Version catalog
├── gradle.properties                              # Build properties
├── PROVISIONING_GUIDE.md                          # Detailed setup instructions
└── README_MDM.md                                  # This file
```

---

## 📦 Dependencies

Key libraries included:

| Library | Purpose | Version |
|---------|---------|---------|
| androidx.core:core-ktx | Android Core APIs | Latest |
| androidx.lifecycle:lifecycle-runtime-ktx | Lifecycle management | Latest |
| androidx.activity:activity-compose | Activity + Compose | Latest |
| androidx.compose.material3:material3 | Material 3 UI | Latest |
| androidx.work:work-runtime-ktx | Background job scheduling | 2.8.1+ |
| com.squareup.retrofit2:retrofit | HTTP client | 2.9.0+ |
| com.squareup.retrofit2:converter-gson | JSON serialization | 2.9.0+ |
| com.google.android.gms:play-services-location | Fused Location API | 21.0.1+ |
| androidx.security:security-crypto | SharedPreferences encryption | Latest |

---

## 🚀 Building the APK

### Prerequisites
- Android Studio 2024.1+
- Android SDK 36 (target API level)
- JDK 11+
- Gradle wrapper (included)

### Build Debug APK
```bash
cd android/
./gradlew assembleDebug
# Output: app/build/outputs/apk/debug/app-debug.apk
```

### Build Release APK (Production)
```bash
cd android/
./gradlew assembleRelease
# Output: app/build/outputs/apk/release/app-release.apk
# Requires signing key configuration
```

### Build with Proguard Minification
```bash
./gradlew assemble --minified
```

---

## 📱 Installation & Enrollment

### Option 1: Direct ADB Install + Device Owner Setup
```bash
# Install APK
adb install -r app/build/outputs/apk/debug/app-debug.apk

# Set as Device Owner (requires fresh device or factory reset)
adb shell dpm set-device-owner com.example.androidmdm/.ElionAdminReceiver

# Verify
adb shell dpm get-device-owner
# Output: com.example.androidmdm/.ElionAdminReceiver
```

### Option 2: Android Enterprise QR Code (Production)
See [PROVISIONING_GUIDE.md](./PROVISIONING_GUIDE.md) for QR code implementation.

### Post-Installation
1. Launch app on device
2. Grant Location Access permission
3. Grant Display Over Other Apps permission
4. Grant Usage Stats Access permission
5. Tap "Complete Enrollment"
6. MDMService automatically starts

---

## 🔧 Configuration

### API Server
Edit `app/src/main/java/com/example/androidmdm/network/RetrofitClient.kt`:
```kotlin
private const val BASE_URL = "http://YOUR_API_SERVER:8000"
```

### Check-in Interval
In `MDMService.kt`:
```kotlin
val workRequest = PeriodicWorkRequestBuilder<CheckInWorker>(15, TimeUnit.MINUTES)
// Change 15 to desired minutes
```

### Device ID
Automatically generated and stored in SharedPreferences. To view:
```bash
adb shell dumpsys app_process | grep ElionMDMPrefs
# Or in code: sharedPreferences.getString("DEVICE_ID", null)
```

---

## 🎯 Supported Remote Commands

The device will execute these commands when received from the backend:

1. **reboot_device** - Restart device
2. **wipe_device** - Factory reset (irreversible)
3. **lock_device** - Enforce password policy
4. **disable_camera** - Disable camera hardware
5. **enable_camera** - Enable camera hardware
6. **kiosk_mode** - Lock to single application
7. **apply_policy** - Apply comprehensive security policy

---

## 📊 Telemetry Data Sent

Each check-in (every 15 minutes) submits:

```json
{
  "device_id": "uuid-string",
  "battery_level": 85.5,
  "is_charging": true,
  "free_disk_space_mb": 2048,
  "installed_apps": ["com.android.settings", "com.example.app", ...],
  "latitude": 40.7128,
  "longitude": -74.0060,
  "foreground_app": "com.example.app",
  "daily_usage_stats": {
    "com.example.app": 3600000,
    "com.android.settings": 120000
  }
}
```

---

## 🔍 Monitoring & Debugging

### View Logs
```bash
adb logcat | grep ElionMDM
```

### Check MDMService Status
```bash
adb shell dumpsys activity services | grep ElionMDM
```

### Verify Device Owner
```bash
adb shell dpm get-device-owner
```

### Test Check-in Manually
```bash
# Trigger immediate check-in
adb shell am startservice com.example.androidmdm/.MDMService
# Wait 5 seconds, then check logs
adb logcat | grep "Check-in"
```

### Clear App Data (Reset)
```bash
adb shell pm clear com.example.androidmdm
# Re-provision as Device Owner after clearing
```

---

## ⚙️ Advanced Configuration

### Enable FCM Push Notifications (Future)
1. Create Firebase project in Google Cloud Console
2. Add google-services.json to `app/`
3. Uncomment FCM code in ElionFirebaseMessagingService.kt
4. Backend registers device token in database

### Custom Kiosk Mode Apps
Edit `PolicyManager.kt` to whitelist additional apps in kiosk mode:
```kotlin
fun setKioskMode(packageName: String, active: Boolean) {
    // Current: Single app only
    // Future: Multiple apps with allowlist
}
```

### Location Accuracy Tuning
In `LocationProvider.kt`:
```kotlin
LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 1000)
// Change to PRIORITY_BALANCED_POWER_ACCURACY for battery savings
```

---

## 🛡️ Security Considerations

⚠️ **Important:**

1. **Never test on production devices** without explicit written authorization
2. **Sign APK with production key** before distributing
3. **Use HTTPS** for all backend API calls
4. **Encrypt sensitive data** stored in SharedPreferences
5. **Implement certificate pinning** for API communication
6. **Regular security audits** of remote command execution
7. **Audit logging** for all device policy changes

---

## 📝 Testing Checklist

- [ ] Device Owner provisioning successful (adb dpm)
- [ ] App launches without crashes
- [ ] All 3 permissions can be granted
- [ ] MDMService starts and runs continuously
- [ ] Check-in logs appear every 15 minutes
- [ ] Remote reboot command executes
- [ ] Remote wipe command works (DON'T TEST ON PROD)
- [ ] Camera disable/enable toggles
- [ ] Location is acquired and reported
- [ ] Battery level updates correctly
- [ ] Installed apps list is complete
- [ ] Foreground app detection works

---

## 🚨 Troubleshooting

| Issue | Solution |
|-------|----------|
| "Device owner not set" | Factory reset and try `adb shell dpm set-device-owner` again |
| MDMService crashes on start | Check if MDM permissions are granted in app settings |
| Check-in fails with 401 | Device ID mismatch or backend token expired |
| Location returns null | Grant background location permission or enable high-accuracy mode |
| Kiosk mode not activating | Ensure device owner is active and app is installed |
| WorkManager not triggering | Check battery optimization settings; may suppress background tasks |

---

## 📚 Resources

- [Android Device Administration API](https://developer.android.com/guide/topics/admin/device-admin)
- [Android Enterprise Documentation](https://developer.android.com/work/requirements)
- [WorkManager Guide](https://developer.android.com/guide/background-tasks/persistent-scheduling)
- [Jetpack Compose Docs](https://developer.android.com/jetpack/compose)
- [Retrofit Documentation](https://square.github.io/retrofit/)

---

## 📞 Support

For issues or questions:
1. Check [PROVISIONING_GUIDE.md](./PROVISIONING_GUIDE.md) first
2. Review logcat output: `adb logcat | grep ElionMDM`
3. Verify device owner: `adb shell dpm get-device-owner`
4. Check backend API connectivity

---

**Last Updated:** March 5, 2026  
**Version:** 1.0.0 (MVP)  
**Status:** Production Ready for Enterprise Deployment
