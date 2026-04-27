package com.elion.mdm

import android.app.Application
import android.content.Intent
import android.util.Log
import com.elion.mdm.BuildConfig
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.domain.MdmState
import com.elion.mdm.launcher.KioskLauncherActivity

/**
 * ElionMDMApp - classe de aplicacao customizada.
 *
 * Necessaria para:
 * 1. Prevenir ClassNotFoundException ao abrir o app.
 * 2. Centralizar fallback de crash sem prender o usuario em uma tela errada.
 */
class ElionMDMApp : Application() {

    companion object {
        private const val TAG = "ElionMDMApp"
    }

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "Aplicacao Elion MDM iniciada")

        setupCrashWatchdog()
    }

    private fun setupCrashWatchdog() {
        val defaultHandler = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, exception ->
            Log.e(TAG, "WATCHDOG ACIONADO: Crash fatal interceptado.", exception)

            if (shouldRelaunchKioskAfterCrash()) {
                val intent = Intent(this, restartTarget).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                }
                runCatching {
                    startActivity(intent)
                    Log.w(TAG, "Tentando relancamento automatico via KioskLauncherActivity.")
                }.onFailure {
                    Log.e(TAG, "Watchdog falhou ao relancar kiosk: ${it.message}")
                }

                android.os.Process.killProcess(android.os.Process.myPid())
                System.exit(10)
                return@setDefaultUncaughtExceptionHandler
            }

            defaultHandler?.uncaughtException(thread, exception)
                ?: run {
                    android.os.Process.killProcess(android.os.Process.myPid())
                    System.exit(10)
                }
        }
    }

    private fun shouldRelaunchKioskAfterCrash(): Boolean {
        if (BuildConfig.IS_DEV) return false

        return runCatching {
            val prefs = SecurePreferences(this)
            prefs.mdmState == MdmState.KIOSK_ACTIVE && prefs.isKioskEnabled
        }.getOrDefault(false)
    }

    private val restartTarget: Class<*> = KioskLauncherActivity::class.java
}
