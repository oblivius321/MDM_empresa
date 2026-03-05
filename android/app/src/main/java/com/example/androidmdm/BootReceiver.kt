package com.example.androidmdm

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import android.os.Build

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_LOCKED_BOOT_COMPLETED) {
            Log.d("ElionMDM", "Dispositivo reiniciado. Iniciando MDMService...")
            
            val serviceIntent = Intent(context, MDMService::class.java)
            
            // Use startForegroundService em Android 8.0+ para evitar background execution limits
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(serviceIntent)
            } else {
                context.startService(serviceIntent)
            }
            
            Log.d("ElionMDM", "MDMService iniciado via BootReceiver")
        }
    }
}
