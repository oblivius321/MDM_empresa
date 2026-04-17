package com.elion.mdm.system

import android.app.admin.DevicePolicyManager
import android.content.Context
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.domain.DevicePolicyHelper
import com.elion.mdm.launcher.KioskLauncherActivity
import org.json.JSONArray

class KioskManager(private val context: Context) {

    companion object {
        private const val TAG = "ElionKioskManager"
    }

    private val dpm = DevicePolicyHelper(context)
    private val prefs = SecurePreferences(context)

    fun enableKiosk(allowedPackages: List<String> = emptyList()) {
        Log.i(TAG, "Ativando modo kiosk (${DevMode.modeHeader()})...")

        // 1. Check Enrollment
        if (prefs.mdmState == com.elion.mdm.domain.MdmState.UNCONFIGURED) {
            Log.e(TAG, "Kiosk bloqueado: Dispositivo nao configurado")
            return
        }

        // 2. Anti-Brick Protection
        if (allowedPackages.isEmpty() && !DevMode.isDevMode()) {
            Log.e(TAG, "Anti-Brick: Ativacao cancelada (nenhum app permitido)")
            return
        }

        if (DevMode.isDevMode()) {
            prefs.isKioskEnabled = true
            prefs.mdmState = com.elion.mdm.domain.MdmState.KIOSK_ACTIVE

            val array = JSONArray()
            allowedPackages.distinct().forEach { array.put(it) }
            prefs.allowedAppsJson = array.toString()

            DevMode.log("Soft kiosk enabled; LockTask and system restrictions are disabled")
            KioskLauncherActivity.launch(context)
            DevMode.showLaunchToast(context)
            return
        }

        if (!dpm.isDeviceOwner()) {
            Log.e(TAG, "App nao e Device Owner; kiosk nao pode ser ativado")
            return
        }

        prefs.isKioskEnabled = true
        prefs.mdmState = com.elion.mdm.domain.MdmState.KIOSK_ACTIVE

        val array = JSONArray()
        allowedPackages.distinct().forEach { array.put(it) }
        prefs.allowedAppsJson = array.toString()

        val packages = (allowedPackages + context.packageName).distinct().toTypedArray()
        dpm.setKioskPackages(packages)
            .onFailure { Log.e(TAG, "Falha ao definir Lock Task packages: ${it.message}") }

        dpm.setLockTaskFeatures(DevicePolicyManager.LOCK_TASK_FEATURE_NONE)
            .onFailure { Log.e(TAG, "Falha ao definir Lock Task features: ${it.message}") }

        dpm.enableFullLockdown()
            .onFailure { Log.e(TAG, "Falha ao aplicar lockdown: ${it.message}") }

        dpm.setStatusBarDisabled(true)
            .onFailure { Log.e(TAG, "Falha ao bloquear status bar: ${it.message}") }
        dpm.disableKeyguard()
            .onFailure { Log.e(TAG, "Falha ao desabilitar keyguard: ${it.message}") }

        KioskLauncherActivity.launch(context)

        Log.i(TAG, "Modo kiosk ativado com ${packages.size} pacote(s)")
    }

    fun disableKiosk() {
        Log.i(TAG, "Desativando modo kiosk...")
        prefs.isKioskEnabled = false
        prefs.mdmState = com.elion.mdm.domain.MdmState.ENROLLED

        if (DevMode.isDevMode()) {
            DevMode.emergencyExit(context)
            Log.i(TAG, "Modo kiosk DEV desativado")
            return
        }

        if (dpm.isDeviceOwner()) {
            dpm.setKioskPackages(emptyArray())
                .onFailure { Log.e(TAG, "Falha ao limpar Lock Task packages: ${it.message}") }
            dpm.disableFullLockdown()
                .onFailure { Log.e(TAG, "Falha ao remover lockdown: ${it.message}") }
            dpm.setStatusBarDisabled(false)
                .onFailure { Log.e(TAG, "Falha ao desbloquear status bar: ${it.message}") }
            dpm.enableKeyguard()
                .onFailure { Log.e(TAG, "Falha ao reativar keyguard: ${it.message}") }
        }

        Log.i(TAG, "Modo kiosk desativado")
    }

    fun isKioskActive(): Boolean = prefs.isKioskEnabled

    fun reapplyIfNeeded() {
        if (!prefs.isKioskEnabled) return

        val allowedPackages = try {
            val array = JSONArray(prefs.allowedAppsJson)
            (0 until array.length()).map { array.getString(it) }
        } catch (_: Exception) {
            emptyList()
        }

        enableKiosk(allowedPackages)
    }
}
