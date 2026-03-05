package com.example.androidmdm

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.UserManager
import android.util.Log

class KioskLauncher(private val context: Context) {
    private val devicePolicyManager = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    private val componentName = ComponentName(context, ElionAdminReceiver::class.java)

    fun setAsDefaultLauncher(enable: Boolean) {
        try {
            if (devicePolicyManager.isAdminActive(componentName)) {
                val intentFilter = IntentFilter(Intent.ACTION_MAIN).apply {
                    addCategory(Intent.category.HOME)
                    addCategory(Intent.category.DEFAULT)
                }

                if (enable) {
                    devicePolicyManager.addPersistentPreferredActivity(
                        componentName,
                        intentFilter,
                        ComponentName(context, MainActivity::class.java)
                    )
                    Log.d("ElionMDM", "Elion DPC definido como Launcher Padrão.")
                } else {
                    devicePolicyManager.clearPackagePersistentPreferredActivities(
                        componentName,
                        context.packageName
                    )
                    Log.d("ElionMDM", "Elion DPC removido de Launcher Padrão.")
                }
            }
        } catch (e: SecurityException) {
             Log.e("ElionMDM", "Erro de segurança ao configurar Launcher Kiosk: ${e.message}")
        }
    }

    fun disableStatusBar(disable: Boolean) {
        try {
             if (devicePolicyManager.isAdminActive(componentName)) {
                 if (devicePolicyManager.isDeviceOwnerApp(context.packageName)) {
                     devicePolicyManager.setStatusBarDisabled(componentName, disable)
                     Log.d("ElionMDM", "Status Bar (Painel de Notificações) desabilitado: $disable")
                 } else {
                      Log.w("ElionMDM", "Desabilitar Status Bar requer privilégios de Device Owner (DO).")
                 }
             }
        } catch (e: SecurityException) {
            Log.e("ElionMDM", "Erro de segurança ao travar Status Bar: ${e.message}")
        }
    }
}
