# Elion MDM - Device Owner Provisioning Guide

In order for the Elion MDM Android DPC (Device Policy Controller) to have full control over the device (e.g., Kiosk Mode, silent app installations, camera disablement, and factory reset), it must be set as the **Device Owner**. 

This elevated privilege cannot be granted through regular permission dialogs. It must be provisioned on a fresh device (or after a factory reset).

## Prerequisites

- Android device with Android 10+ (API 29+)
- No Google account or corporate MDM previously set up
- USB cable for ADB connection
- Android SDK Platform Tools installed locally

## Method 1: ADB (For Development & Testing)

This is the fastest method for developers testing the MDM application on physical devices or emulators. Note that the device *cannot* have any other accounts (like Google accounts) registered before running this command.

### Steps

1. **Install the APK via Android Studio or ADB:**
   ```bash
   adb install -r app-debug.apk
   ```
   Or directly from Android Studio: Run → Run 'app'

2. **Set the application as the Device Owner using adb shell dpm:**
   ```bash
   adb shell dpm set-device-owner com.example.androidmdm/.ElionAdminReceiver
   ```
   
   **Expected output on success:**
   ```
   Success: Device owner set to package com.example.androidmdm for user 0
   ```

   **If you get "Error: Unexpected error..." error:**
   - Ensure device is not connected to any Google account
   - Device must be fresh or factory reset
   - Re-try the command

3. **Verify the Device Owner was set:**
   ```bash
   adb shell dpm get-device-owner
   ```
   Should output: `com.example.androidmdm/.ElionAdminReceiver`

4. **Open the app and complete onboarding:**
   - Grant Location Access permission
   - Grant Display Over Other Apps permission
   - Grant Usage Stats Access permission
   - Tap "Complete Enrollment"

5. **Verify MDM Service is Running:**
   ```bash
   adb shell dumpsys activity services | grep ElionMDM
   ```

The device is now enrolled as a Device Owner and will:
- Automatically check in every 15 minutes
- Execute remote policies (lock, wipe, reboot, kiosk mode, etc.)
- Report battery level, disk space, installed apps, and location

### Troubleshooting ADB Setup

**Problem:** "Error setting device admin: Not an admin receiver"
- Solution: Ensure AndroidManifest.xml declares ElionAdminReceiver with BIND_DEVICE_ADMIN permission

**Problem:** "Error: User restriction not allowed"
- Solution: Device likely has another MDM or DPC active. Factory reset and try again.

**Problem:** ADB connection refused
- Solution: Enable USB Debugging in Developer Options and authorize the connected computer.

---

## Method 2: QR Code Provisioning (Production)

For mass deployment, Android Enterprise supports QR Code Provisioning from the "Hi There" initial setup screen on a factory-reset device.

### How It Works

1. User factory-resets device
2. On initial setup, user taps the welcome screen 6-7 times in the same area to trigger QR Code reader
3. Connects to Wi-Fi
4. Scans a QR code containing JSON enrollment payload
5. Android downloads the APK from the URL in the payload
6. DPC becomes the Device Owner automatically

### QR Payload Format

```json
{
  "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME": "com.example.androidmdm/.ElionAdminReceiver",
  "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION": "https://mdm.company.com/elion-mdm.apk",
  "android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE": {
    "device_id": "DEVICE-SERIAL-NUMBER",
    "enrollment_server": "https://api.mdm.company.com"
  }
}
```

### Implementation (Future Backend Task)

To generate QR codes dynamically, the backend should:

1. Create an endpoint `/api/qr/provisioning` that accepts device info
2. Generate the JSON payload above
3. Encode it using Base64URL
4. Generate a QR code PNG using a library like `qrcode` (Python)
5. Return the QR code image and shareable provisioning link

**Example Python snippet (future):**
```python
import qrcode
import json
import base64

payload = {
    "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME": "com.example.androidmdm/.ElionAdminReceiver",
    "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION": "https://mdm.company.com/elion-mdm.apk"
}

qr = qrcode.QRCode(version=1, box_size=10, border=5)
qr.add_data(json.dumps(payload))
qr.make(fit=True)
img = qr.make_image(fill_color="black", back_color="white")
img.save("provisioning_qr.png")
```

---

## Supported Commands

Once enrolled, the device will respond to these MDM commands:

- **reboot_device** - Restart the device
- **wipe_device** - Factory reset (irreversible)
- **lock_device** - Enforce strong password requirement
- **disable_camera** - Block camera hardware
- **enable_camera** - Re-enable camera hardware
- **kiosk_mode** - Lock device to single app
- **apply_policy** - Apply global security policy

---

## Security Notes

- Device Owner privileges are permanent until device reset or MDM uninstall (which requires additional auth)
- Never test MD M on production devices without explicit approval
- Ensure APK is signed with production key before distributing
- Keep the MDM backend API behind HTTPS and authentication

---

## Advanced: Firebase Cloud Messaging (FCM)

For real-time command delivery (currently implemented with 15-minute polling), Firebase Cloud Messaging can be integrated:

1. Configure Firebase project in Google Console
2. Register FCM token in ElionFirebaseMessagingService.kt
3. Backend sends `send` requests via Firebase Admin SDK
4. Device receives commands instantly instead of waiting 15 minutes

Status: Implementation ready but not yet integrated into backend.
