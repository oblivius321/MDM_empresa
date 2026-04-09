package com.elion.mdm.system

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import kotlinx.coroutines.DelicateCoroutinesApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.GlobalScope
import kotlinx.coroutines.launch
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

    @OptIn(DelicateCoroutinesApi::class)
    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action ?: return

        Log.i(TAG, "Broadcast recebido: $action")

        when (action) {
            Intent.ACTION_BOOT_COMPLETED,
            Intent.ACTION_LOCKED_BOOT_COMPLETED,
            "android.intent.action.MY_PACKAGE_REPLACED" -> {
                val pendingResult = goAsync()
                GlobalScope.launch(Dispatchers.IO) {
                    try {
                        handleBoot(context)
                    } finally {
                        pendingResult.finish()
                    }
                }
            }
        }
    }

    private suspend fun handleBoot(context: Context) {
        val prefs = SecurePreferences(context)

        // 1. Checagem Atômica da Enrollment State Machine
        val (state, meta) = com.elion.mdm.system.EnrollmentStateMachine.getCurrentState(context)
        Log.i(TAG, "Boot State Machine Check: $state")

        if (state == com.elion.mdm.system.EnrollmentState.ERROR_RECOVERY) {
            Log.e(TAG, "Boot fallback: Agente em ERROR_RECOVERY. Recuperação manual/automática em breve.")
        } else if (state == com.elion.mdm.system.EnrollmentState.BOOTSTRAPPED || state == com.elion.mdm.system.EnrollmentState.ENROLLING) {
            Log.w(TAG, "Boot fallback: Device restart detectado durante o Enrollment. Retomando processo...")
            // Aqui uma invocação do enrollment ocorrerá automaticamente pela service central
        }

        // 2. Se kiosk está ativo, re-aplicar lockdown e lançar launcher
        if (prefs.isKioskEnabled || state == com.elion.mdm.system.EnrollmentState.KIOSK_APPLIED || state == com.elion.mdm.system.EnrollmentState.OPERATIONAL) {
            Log.i(TAG, "Kiosk ativo (ou estado Operational) — re-aplicando lockdown após boot")
            try {
                val kioskManager = com.elion.mdm.system.KioskManager(context)
                kioskManager.reapplyIfNeeded()
            } catch (e: Exception) {
                Log.e(TAG, "Falha ao re-aplicar kiosk: ${e.message}")
            }
            // Lança a activity do kiosk ativamente para garantir a frente
            KioskLauncherActivity.launch(context)
        }

        // 3. Iniciar o MDM Foreground Service (sempre) para capturar o WebSocket
        try {
            MDMForegroundService.start(context)
            Log.i(TAG, "MDMForegroundService iniciado após boot")
        } catch (e: Exception) {
            Log.e(TAG, "Falha ao iniciar MDMForegroundService: ${e.message}")
        }
    }
}
