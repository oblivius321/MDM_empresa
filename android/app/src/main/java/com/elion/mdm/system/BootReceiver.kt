package com.elion.mdm.system

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.domain.usecase.EnrollDeviceUseCase
import com.elion.mdm.launcher.KioskLauncherActivity
import com.elion.mdm.services.MDMForegroundService
import kotlinx.coroutines.DelicateCoroutinesApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.GlobalScope
import kotlinx.coroutines.launch

class BootReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "ElionBootReceiver"
        private const val MAX_ENROLLMENT_RESUME_AGE_MS = 15 * 60 * 1000L
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
        val stateInfo = MDMStateMachine.getStateInfo(context)
        val state = stateInfo.state

        Log.i(TAG, "Boot State Machine Check: $state")

        if (state == MDMState.ERROR) {
            Log.e(TAG, "Boot fallback: agente em ERROR.")
        } else if (state == MDMState.REGISTERING) {
            Log.w(TAG, "Boot fallback: retomando enrollment interrompido.")
            val bootstrapToken = stateInfo.metadata["bootstrap_token"]
            val apiUrl = stateInfo.metadata["api_url"]
            if (!bootstrapToken.isNullOrBlank() && !apiUrl.isNullOrBlank()) {
                val stateAgeMs = System.currentTimeMillis() - stateInfo.timestamp
                if (stateInfo.isInCooldown() || stateAgeMs > MAX_ENROLLMENT_RESUME_AGE_MS) {
                    Log.w(TAG, "Boot fallback ignorado: token de enrollment pendente esta expirado ou em cooldown.")
                    MDMStateMachine.transitionTo(
                        context,
                        MDMState.ERROR,
                        error = "stale_enrollment_token_not_retried"
                    )
                    return
                }

                EnrollDeviceUseCase(context.applicationContext).enroll(
                    bootstrapToken,
                    apiUrl,
                    stateInfo.metadata["profile_id"]?.takeIf { it.isNotBlank() }
                )
            }
        }

        if (prefs.isKioskEnabled || state == MDMState.ENFORCING || state == MDMState.OPERATIONAL) {
            Log.i(TAG, "Kiosk ativo ou operacional; reaplicando lockdown apos boot")
            try {
                KioskManager(context).reapplyIfNeeded()
            } catch (e: Exception) {
                Log.e(TAG, "Falha ao re-aplicar kiosk: ${e.message}")
            }
            KioskLauncherActivity.launch(context)
        }

        try {
            MDMForegroundService.start(context)
            Log.i(TAG, "MDMForegroundService iniciado apos boot")
        } catch (e: Exception) {
            Log.e(TAG, "Falha ao iniciar MDMForegroundService: ${e.message}")
        }
    }
}
