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
        
        // Espaço para inicialização de Crashlytics, Hilt, WorkManager, etc.
    }
}
