package com.elion.mdm

import android.app.admin.DeviceAdminReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.services.MDMForegroundService

/**
 * AdminReceiver — ponto de entrada do Device Owner (DPC).
 *
 * Registrado no AndroidManifest.xml com:
 *   <receiver android:name=".AdminReceiver"
 *             android:permission="android.permission.BIND_DEVICE_ADMIN">
 *       <meta-data android:name="android.app.device_admin"
 *                  android:resource="@xml/device_admin_policies"/>
 *       <intent-filter>
 *           <action android:name="android.app.action.DEVICE_ADMIN_ENABLED"/>
 *       </intent-filter>
 *   </receiver>
 *
 * Ativação como Device Owner via ADB (uma única vez por dispositivo factory-reset):
 *   adb shell dpm set-device-owner com.elion.mdm/.AdminReceiver
 *
 * ─── Por que Device Owner? ────────────────────────────────────────────────────
 * Device Owner (DO) é o nível máximo de controle no Android Enterprise.
 * Diferente de um Device Admin comum, o DO pode:
 *   • Bloquear tela remotamente        → dpm.lockNow()
 *   • Apagar todos os dados            → dpm.wipeData(flags)
 *   • Habilitar Kiosk Mode             → setLockTaskPackages + startLockTask()
 *   • Desativar câmera globalmente     → dpm.setCameraDisabled(true)
 *   • Desativar status bar             → dpm.setStatusBarDisabled(true)
 *   • Instalar APKs silenciosamente    → PackageInstaller com DO session
 *   • Reiniciar o dispositivo          → dpm.reboot()
 *   • Aplicar restrições de usuário    → UserManager.DISALLOW_*
 *
 * Nenhuma dessas APIs funciona para apps comuns — apenas DO ou Profile Owner.
 */
class AdminReceiver : DeviceAdminReceiver() {

    companion object {
        private const val TAG = "ElionAdminReceiver"
    }

    override fun onEnabled(context: Context, intent: Intent) {
        super.onEnabled(context, intent)
        Log.i(TAG, "Device Admin HABILITADO")
    }

    override fun onDisabled(context: Context, intent: Intent) {
        super.onDisabled(context, intent)
        Log.w(TAG, "Device Admin DESABILITADO — limpando estado local")
        SecurePreferences(context).clearAll()
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
        val intent = Intent(context, MDMForegroundService::class.java)
        context.startForegroundService(intent)
    }
}
