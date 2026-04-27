package com.elion.mdm.system

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.widget.Toast
import com.elion.mdm.BuildConfig
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.domain.DevicePolicyHelper
import com.elion.mdm.services.MDMForegroundService

object DevMode {
    private const val TAG = "MDM_DEV_MODE"
    private const val LAUNCH_TOAST_MIN_INTERVAL_MS = 10_000L
    private const val SAFE_LAUNCH_MESSAGE =
        "DEV MODE: soft kiosk ativo; bloqueios criticos foram pulados"
    private var lastLaunchToastAt = 0L

    fun isDevMode(): Boolean = BuildConfig.IS_DEV

    fun modeHeader(): String = if (isDevMode()) "DEV" else "PROD"

    fun log(message: String) {
        if (isDevMode()) {
            Log.d(TAG, message)
        }
    }

    fun applyPolicySafe(actionName: String, action: () -> Unit) {
        if (isDevMode()) {
            blockDangerousPolicy(actionName)
            return
        }
        action()
    }

    fun blockDangerousPolicy(actionName: String) {
        Log.w(TAG, "Skipped hard-lock policy in DEV build: $actionName")
    }

    fun softKioskSummary(): String =
        "DEV soft-kiosk: Lock Task, app hiding and mobile-network lockdown stay disabled"

    fun safeLaunchMessage(): String = SAFE_LAUNCH_MESSAGE

    fun shouldShowLaunchToast(): Boolean {
        val now = System.currentTimeMillis()
        if (now - lastLaunchToastAt < LAUNCH_TOAST_MIN_INTERVAL_MS) {
            return false
        }
        lastLaunchToastAt = now
        return true
    }

    fun showLaunchToast(context: Context) {
        if (!isDevMode() || !shouldShowLaunchToast()) return
        showToast(context, SAFE_LAUNCH_MESSAGE)
    }

    fun emergencyExit(context: Context) {
        if (!isDevMode()) return

        val appContext = context.applicationContext
        Log.w(TAG, "Emergency exit requested in DEV build")

        runCatching {
            SecurePreferences(appContext).isKioskEnabled = false
        }.onFailure {
            Log.e(TAG, "Failed to clear kiosk flag: ${it.message}")
        }

        runCatching {
            val dpm = DevicePolicyHelper(appContext)
            dpm.setStatusBarDisabled(false)
            dpm.enableKeyguard()
            dpm.disableFullLockdown()
            dpm.clearSafetyRestrictions()
            dpm.setKioskPackages(emptyArray())
        }.onFailure {
            Log.e(TAG, "Failed to clear DEV policies: ${it.message}")
        }

        runCatching {
            MDMForegroundService.stop(appContext)
        }.onFailure {
            Log.e(TAG, "Failed to stop service in DEV exit: ${it.message}")
        }

        showToast(appContext, "DEV MODE: kiosk exited")
    }

    private fun showToast(context: Context, message: String) {
        Handler(Looper.getMainLooper()).post {
            Toast.makeText(context.applicationContext, message, Toast.LENGTH_LONG).show()
        }
    }
}
