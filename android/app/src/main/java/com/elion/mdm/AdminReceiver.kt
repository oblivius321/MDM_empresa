package com.elion.mdm

import android.app.admin.DeviceAdminReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.util.Log
import kotlinx.coroutines.DelicateCoroutinesApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.GlobalScope
import kotlinx.coroutines.launch
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.services.MDMForegroundService

/**
 * AdminReceiver — Ponto de entrada obrigatório para o Device Owner (DPC).
 * 
 * Implementação corrigida para compatibilidade total com o comando:
 * adb shell dpm set-device-owner com.elion.mdm/.AdminReceiver
 */
class AdminReceiver : DeviceAdminReceiver() {

    companion object {
        private const val TAG = "ElionAdminReceiver"

        fun getComponentName(context: Context): ComponentName {
            return ComponentName(context.applicationContext, AdminReceiver::class.java)
        }
    }

    override fun onEnabled(context: Context, intent: Intent) {
        super.onEnabled(context, intent)
        Log.i(TAG, "✅ Device Admin HABILITADO")
    }

    override fun onDisabled(context: Context, intent: Intent) {
        super.onDisabled(context, intent)
        Log.w(TAG, "⚠️ Device Admin DESABILITADO — Limpando dados locais de segurança")
        try {
            SecurePreferences(context).clearAll()
        } catch (e: Exception) {
            Log.e(TAG, "Erro ao limpar preferências: ${e.message}")
        }
    }

    @OptIn(DelicateCoroutinesApi::class)
    override fun onProfileProvisioningComplete(context: Context, intent: Intent) {
        super.onProfileProvisioningComplete(context, intent)
        Log.i(TAG, "🚀 Provisionamento Zero-Touch concluído — Lendo Bundle Extras")
        
        val pendingResult = goAsync()
        GlobalScope.launch(Dispatchers.IO) {
            try {
                val bundle = intent.getParcelableExtra<android.os.PersistableBundle>(android.app.admin.DevicePolicyManager.EXTRA_PROVISIONING_ADMIN_EXTRAS_BUNDLE)
                
                val bootstrapToken = bundle?.getString("bootstrap_token") ?: ""
                val apiUrl = bundle?.getString("api_url") ?: ""
                val profileId = bundle?.getString("profile_id") ?: ""
                
                Log.d(TAG, "Provisioning Bundle Recebido -> token_presente=${bootstrapToken.isNotEmpty()}, api=$apiUrl, profile=$profileId")
                
                // Inicia o state machine blindado
                com.elion.mdm.system.EnrollmentStateMachine.transitionTo(
                    context, 
                    com.elion.mdm.system.EnrollmentState.BOOTSTRAPPED,
                    mapOf(
                        "bootstrap_token" to bootstrapToken,
                        "api_url" to apiUrl,
                        "profile_id" to profileId
                    )
                )
                
                startMDMService(context)
            } catch (e: Exception) {
                Log.e(TAG, "Erro grave no Bootstrapping do QR: ${e.message}")
                com.elion.mdm.system.EnrollmentStateMachine.transitionTo(
                    context, 
                    com.elion.mdm.system.EnrollmentState.ERROR_RECOVERY,
                    mapOf("error" to "bootstrapping_failed", "details" to (e.message ?: ""))
                )
            } finally {
                pendingResult.finish()
            }
        }
    }

    override fun onLockTaskModeEntering(context: Context, intent: Intent, pkg: String) {
        super.onLockTaskModeEntering(context, intent, pkg)
        Log.i(TAG, "🔒 Kiosk Mode ATIVADO para: $pkg")
    }

    override fun onLockTaskModeExiting(context: Context, intent: Intent) {
        super.onLockTaskModeExiting(context, intent)
        Log.w(TAG, "🔓 Kiosk Mode DESATIVADO")
    }

    override fun onPasswordFailed(context: Context, intent: Intent, user: android.os.UserHandle) {
        super.onPasswordFailed(context, intent, user)
        Log.w(TAG, "❌ Tentativa de senha FALHOU — Usuário: $user")
    }

    private fun startMDMService(context: Context) {
        try {
            val serviceIntent = Intent(context, MDMForegroundService::class.java)
            context.startForegroundService(serviceIntent)
        } catch (e: Exception) {
            Log.e(TAG, "Erro ao iniciar MDM Service: ${e.message}")
        }
    }
}
