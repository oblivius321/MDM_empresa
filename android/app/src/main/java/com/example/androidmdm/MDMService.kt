package com.example.androidmdm

import android.app.Service
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.example.androidmdm.network.CheckInPayload
import com.example.androidmdm.network.RetrofitClient
import androidx.work.*
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.*
import java.util.UUID

class MDMService : Service() {

    private val serviceScope = CoroutineScope(Dispatchers.IO + Job())
    private lateinit var policyManager: PolicyManager
    private lateinit var inventoryManager: InventoryManager
    private lateinit var sharedPreferences: SharedPreferences
    
    // Advanced DPC Providers
    private lateinit var locationProvider: LocationProvider
    private lateinit var activityMonitor: ActivityMonitor
    private lateinit var overlayManager: OverlayManager
    private lateinit var kioskLauncher: KioskLauncher
    private lateinit var screenCaptureManager: ScreenCaptureManager

    companion object {
        const val NOTIFICATION_ID = 100
        const val NOTIFICATION_CHANNEL_ID = "ElionMDMService"
    }

    override fun onCreate() {
        super.onCreate()
        policyManager = PolicyManager(this)
        inventoryManager = InventoryManager(this)
        sharedPreferences = getSharedPreferences("ElionMDMPrefs", Context.MODE_PRIVATE)
        
        // Initialize Advanced Providers
        locationProvider = LocationProvider(this)
        activityMonitor = ActivityMonitor(this)
        overlayManager = OverlayManager(this)
        kioskLauncher = KioskLauncher(this)
        screenCaptureManager = ScreenCaptureManager(this)
        
        Log.d("ElionMDM", "MDMService Criado.")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.d("ElionMDM", "MDMService Iniciado. Configurando Loop de Check-in...")
        
        // Create foreground notification
        startForegroundNotification()
        
        // Start check-in loop
        startCheckInLoop()
        
        return START_STICKY
    }

    private fun startForegroundNotification() {
        // Create notification channel for Android 8.0+
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                "Elion MDM Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Monitoring device compliance and executing policies"
            }
            getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
        }

        val notification = NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setContentTitle("Elion MDM")
            .setContentText("Device management service running")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

        startForeground(NOTIFICATION_ID, notification)
        Log.d("ElionMDM", "Foreground notification started")
    }

    private fun startCheckInLoop() {
        // Initialize device ID if not exists
        getOrCreateDeviceId()
        
        // Create work request with exponential backoff
        val workRequest = PeriodicWorkRequestBuilder<CheckInWorker>(15, TimeUnit.MINUTES)
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .setRequiresBatteryNotLow(false)
                    .build()
            )
            .setBackoffPolicy(BackoffPolicy.EXPONENTIAL, 1, TimeUnit.MINUTES)
            .build()
            
        WorkManager.getInstance(applicationContext).enqueueUniquePeriodicWork(
            "ElionMDMCheckIn",
            ExistingPeriodicWorkPolicy.KEEP,
            workRequest
        )
        Log.d("ElionMDM", "WorkManager agendado para rodar a cada 15 min com backoff exponencial")
        
        // Run check-in immediately for first time
        runCheckInImmediately()
    }

    private fun runCheckInImmediately() {
        serviceScope.launch {
            try {
                Log.d("ElionMDM", "Executando check-in imediato...")
                val deviceId = getOrCreateDeviceId()
                
                val inventoryManager = InventoryManager(this@MDMService)
                val locationProvider = LocationProvider(this@MDMService)
                val activityMonitor = ActivityMonitor(this@MDMService)
                
                val inv = inventoryManager.getInventory()
                val location = locationProvider.getCurrentLocation()
                
                val payload = CheckInPayload(
                    battery_level = inv.batteryLevel,
                    is_charging = inv.isCharging,
                    free_disk_space_mb = inv.availableStorage,
                    installed_apps = inv.installedPackages,
                    latitude = location?.latitude,
                    longitude = location?.longitude,
                    foreground_app = activityMonitor.getForegroundApp(),
                    daily_usage_stats = activityMonitor.getDailyUsageStats()
                )
                
                val response = RetrofitClient.api.sendCheckIn(deviceId, payload)
                if (response.isSuccessful) {
                    Log.d("ElionMDM", "Check-in imediato bem-sucedido: $deviceId")
                } else {
                    Log.w("ElionMDM", "Check-in imediato falhou. HTTP ${response.code()}")
                }
            } catch (e: Exception) {
                Log.e("ElionMDM", "Erro no check-in imediato: ${e.message}", e)
            }
        }
    }

    private fun getOrCreateDeviceId(): String {
        var deviceId = sharedPreferences.getString("DEVICE_ID", null)
        if (deviceId == null) {
            deviceId = UUID.randomUUID().toString()
            sharedPreferences.edit().putString("DEVICE_ID", deviceId).apply()
            Log.d("ElionMDM", "Novo DeviceID gerado: $deviceId")
        }
        return deviceId
    }

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
        Log.d("ElionMDM", "MDMService Destruído.")
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null // Não é um Bound Service
    }
}
