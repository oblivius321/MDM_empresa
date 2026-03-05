package com.example.androidmdm

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.util.Log

class PolicyManager(private val context: Context) {
    private val devicePolicyManager = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    private val componentName = ComponentName(context, ElionAdminReceiver::class.java)

    fun toggleCamera(enabled: Boolean) {
        try {
            if (devicePolicyManager.isAdminActive(componentName)) {
                devicePolicyManager.setCameraDisabled(componentName, !enabled)
                Log.d("ElionMDM", "Câmera ativada: $enabled")
            } else {
                Log.e("ElionMDM", "Privilégios de administrador não estão ativos.")
            }
        } catch (e: SecurityException) {
            Log.e("ElionMDM", "Erro de segurança ao alterar câmera: ${e.message}")
        }
    }

    fun wipeData(factoryReset: Boolean) {
        try {
            if (devicePolicyManager.isAdminActive(componentName)) {
                val flags = if (factoryReset) DevicePolicyManager.WIPE_RESET_PROTECTION_DATA else 0
                devicePolicyManager.wipeData(flags)
                Log.d("ElionMDM", "Wipe data acionado (Factory Reset = $factoryReset)")
            }
        } catch (e: SecurityException) {
            Log.e("ElionMDM", "Erro de segurança no Wipe: ${e.message}")
        }
    }

    fun setKioskMode(packageName: String, active: Boolean) {
        try {
            if (devicePolicyManager.isAdminActive(componentName)) {
                if (active) {
                    devicePolicyManager.setLockTaskPackages(componentName, arrayOf(packageName))
                    Log.d("ElionMDM", "Kiosk mode ativado para: $packageName")
                } else {
                    devicePolicyManager.setLockTaskPackages(componentName, emptyArray())
                    Log.d("ElionMDM", "Kiosk mode desativado.")
                }
            }
        } catch (e: SecurityException) {
            Log.e("ElionMDM", "Erro de segurança no Kiosk mode: ${e.message}")
        }
    }

    fun enforcePasswordQuality() {
        try {
            if (devicePolicyManager.isAdminActive(componentName)) {
                devicePolicyManager.setPasswordQuality(componentName, DevicePolicyManager.PASSWORD_QUALITY_COMPLEX)
                devicePolicyManager.setPasswordMinimumLength(componentName, 6)
                Log.d("ElionMDM", "Qualidade de senha imposta: COMPLEXA, Mín. 6 dígitos")
            }
        } catch (e: SecurityException) {
            Log.e("ElionMDM", "Erro de segurança ao impor senha: ${e.message}")
        }
    }

    fun rebootDevice() {
        try {
            if (devicePolicyManager.isAdminActive(componentName)) {
                devicePolicyManager.reboot(componentName)
                Log.d("ElionMDM", "Reboot acionado.")
            }
        } catch (e: SecurityException) {
            Log.e("ElionMDM", "Erro de segurança ao reiniciar: ${e.message}")
        }
    }
}
