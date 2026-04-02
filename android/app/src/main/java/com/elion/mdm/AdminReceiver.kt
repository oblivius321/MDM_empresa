package com.elion.mdm

import android.app.admin.DeviceAdminReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.util.Log
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

    override fun onProfileProvisioningComplete(context: Context, intent: Intent) {
        super.onProfileProvisioningComplete(context, intent)
        Log.i(TAG, "🚀 Provisionamento concluído — Iniciando MDM Service")
        startMDMService(context)
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
