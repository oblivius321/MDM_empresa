package com.elion.mdm

import android.app.admin.DeviceAdminReceiver as AndroidDeviceAdminReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.services.MDMForegroundService

/**
 * DeviceAdminReceiver — ponto de entrada do Device Owner (DPC).
 *
 * Ativação como Device Owner via ADB (uma única vez por dispositivo factory-reset):
 *   adb shell dpm set-device-owner com.elion.mdm/.DeviceAdminReceiver
 */
class DeviceAdminReceiver : AndroidDeviceAdminReceiver() {

    companion object {
        private const val TAG = "ElionDeviceAdminReceiver"

        fun getComponentName(context: Context): ComponentName {
            return ComponentName(context.applicationContext, DeviceAdminReceiver::class.java)
        }
    }

    override fun onEnabled(context: Context, intent: Intent) {
        super.onEnabled(context, intent)
        Log.i(TAG, "Device Admin HABILITADO")
    }

    override fun onDisabled(context: Context, intent: Intent) {
        super.onDisabled(context, intent)
        Log.w(TAG, "Device Admin DESABILITADO — limpando estado local")
        try {
            SecurePreferences(context).clearAll()
        } catch (e: Exception) {
            Log.e(TAG, "Erro ao limpar preferências: ${e.message}")
        }
    }

    override fun onProfileProvisioningComplete(context: Context, intent: Intent) {
        super.onProfileProvisioningComplete(context, intent)
        Log.i(TAG, "Provisionamento concluído — iniciando MDM Service")
        startMDMService(context)
    }

    override fun onLockTaskModeEntering(context: Context, intent: Intent, pkg: String) {
        super.onLockTaskModeEntering(context, intent, pkg)
        Log.i(TAG, "Kiosk Mode ATIVADO para: $pkg")
    }

    override fun onLockTaskModeExiting(context: Context, intent: Intent) {
        super.onLockTaskModeExiting(context, intent)
        Log.i(TAG, "Kiosk Mode DESATIVADO")
    }

    override fun onPasswordFailed(context: Context, intent: Intent, user: android.os.UserHandle) {
        super.onPasswordFailed(context, intent, user)
        Log.w(TAG, "Tentativa de senha FALHOU — usuário: $user")
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
