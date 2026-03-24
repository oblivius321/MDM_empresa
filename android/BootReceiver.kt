package com.elion.mdm.system

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.launcher.KioskLauncherActivity
import com.elion.mdm.services.MDMForegroundService

/**
 * BootReceiver — recebe broadcast de boot e reaplica o kiosk + MDM service.
 *
 * Registrado no AndroidManifest com:
 *   <action android:name="android.intent.action.BOOT_COMPLETED"/>
 *   <action android:name="android.intent.action.LOCKED_BOOT_COMPLETED"/>
 *   <action android:name="android.intent.action.MY_PACKAGE_REPLACED"/>
 *
 * Fluxo:
 *   1. Boot completo → verificar se kiosk está ativo
 *   2. Se ativo → re-aplicar kiosk (KioskManager.reapplyIfNeeded)
 *   3. Sempre → iniciar MDMForegroundService
 */
class BootReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "ElionBootReceiver"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action ?: return

        Log.i(TAG, "Broadcast recebido: $action")

        when (action) {
            Intent.ACTION_BOOT_COMPLETED,
            Intent.ACTION_LOCKED_BOOT_COMPLETED,
            "android.intent.action.MY_PACKAGE_REPLACED" -> {
                handleBoot(context)
            }
        }
    }

    private fun handleBoot(context: Context) {
        val prefs = SecurePreferences(context)

        // 1. Se kiosk está ativo, re-aplicar lockdown e lançar launcher
        if (prefs.isKioskEnabled) {
            Log.i(TAG, "Kiosk ativo — re-aplicando modo kiosk após boot")
            try {
                val kioskManager = KioskManager(context)
                kioskManager.reapplyIfNeeded()
            } catch (e: Exception) {
                Log.e(TAG, "Falha ao re-aplicar kiosk: ${e.message}")
                // Fallback: pelo menos lançar a activity do kiosk
                KioskLauncherActivity.launch(context)
            }
        }

        // 2. Iniciar o MDM Foreground Service (sempre)
        try {
            MDMForegroundService.start(context)
            Log.i(TAG, "MDMForegroundService iniciado após boot")
        } catch (e: Exception) {
            Log.e(TAG, "Falha ao iniciar MDMForegroundService: ${e.message}")
        }
    }
}
