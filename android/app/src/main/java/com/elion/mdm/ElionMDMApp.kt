package com.elion.mdm

import android.app.Application
import android.util.Log

/**
 * ElionMDMApp — classe de aplicação customizada.
 * 
 * Necessária para:
 *   1. Prevenir ClassNotFoundException ao abrir o app (conforme AndroidManifest.xml)
 *   2. Inicializar componentes globais se necessário
 */
class ElionMDMApp : Application() {
    
    companion object {
        private const val TAG = "ElionMDMApp"
    }

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "Aplicação Elion MDM iniciada")
        
        setupCrashWatchdog()
    }

    private fun setupCrashWatchdog() {
        Thread.setDefaultUncaughtExceptionHandler { _, exception ->
            Log.e(TAG, "🔥 WATCHDOG ACIONADO: Crash Fatal Interceptado!", exception)
            
            val intent = android.content.Intent(this, com.elion.mdm.launcher.KioskLauncherActivity::class.java).apply {
                addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK or android.content.Intent.FLAG_ACTIVITY_CLEAR_TASK)
            }
            
            try {
                startActivity(intent)
                Log.w(TAG, "Tentando relançamento automático via KioskLauncher...")
            } catch (e: Exception) {
                Log.e(TAG, "Watchdog falhou ao relançar a activity: ${e.message}")
            }
            
            android.os.Process.killProcess(android.os.Process.myPid())
            System.exit(10)
        }
    }
}
