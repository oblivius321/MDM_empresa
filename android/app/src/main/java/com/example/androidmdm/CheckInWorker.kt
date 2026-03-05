package com.example.androidmdm

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.example.androidmdm.network.CheckInPayload
import com.example.androidmdm.network.CommandStatusPayload
import com.example.androidmdm.network.RetrofitClient
import com.google.gson.JsonObject

class CheckInWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): Result {
        Log.d("ElionMDM", "WorkManager executando Check-in em background (tentativa ${runAttemptCount + 1})...")
        return try {
            val sharedPreferences = applicationContext.getSharedPreferences("ElionMDMPrefs", Context.MODE_PRIVATE)
            val deviceId = sharedPreferences.getString("DEVICE_ID", null) 
                ?: return Result.failure()

            val inventoryManager = InventoryManager(applicationContext)
            val locationProvider = LocationProvider(applicationContext)
            val activityMonitor = ActivityMonitor(applicationContext)
            val policyManager = PolicyManager(applicationContext)

            // Collect device inventory
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

            // Send check-in
            val checkInResponse = try {
                RetrofitClient.api.sendCheckIn(deviceId, payload)
            } catch (e: Exception) {
                Log.e("ElionMDM", "Erro ao enviar check-in: ${e.message}")
                return Result.retry() // Retry on network error
            }

            if (!checkInResponse.isSuccessful) {
                Log.e("ElionMDM", "Check-in falhou. HTTP ${checkInResponse.code()}")
                return if (checkInResponse.code() >= 500) {
                    Result.retry() // Retry on server error
                } else {
                    Result.failure() // Fail on client error
                }
            }

            Log.d("ElionMDM", "Check-in concluído com sucesso: $deviceId")
            
            // Fetch and execute pending commands
            try {
                val cmdsResponse = RetrofitClient.api.getPendingCommands(deviceId)
                if (cmdsResponse.isSuccessful) {
                    val commands = cmdsResponse.body() ?: emptyList()
                    Log.d("ElionMDM", "Recebidos ${commands.size} comandos pendentes")
                    
                    for (cmd in commands) {
                        executeCommand(policyManager, cmd, deviceId)
                        
                        // Report command status
                        try {
                            RetrofitClient.api.updateCommandStatus(
                                deviceId,
                                cmd.id,
                                CommandStatusPayload("completed", "Success")
                            )
                            Log.d("ElionMDM", "Comando ${cmd.command} (ID: ${cmd.id}) marcado como completed")
                        } catch (e: Exception) {
                            Log.e("ElionMDM", "Erro ao reportar status do comando: ${e.message}")
                            // Continue with next command
                        }
                    }
                } else {
                    Log.w("ElionMDM", "Falha ao buscar comandos. HTTP ${cmdsResponse.code()}")
                }
            } catch (e: Exception) {
                Log.e("ElionMDM", "Erro ao buscar/executar comandos: ${e.message}")
                // Don't retry just for command execution failure
            }

            Result.success()
        } catch (e: Exception) {
            Log.e("ElionMDM", "Erro crítico no WorkManager: ${e.message}", e)
            // Retry with exponential backoff (configured in MDMService)
            if (runAttemptCount < 3) {
                Result.retry()
            } else {
                Result.failure()
            }
        }
    }

    private suspend fun executeCommand(policyManager: PolicyManager, cmd: Any, deviceId: String) {
        try {
            val cmdReflection = cmd as? Any
            val commandName = cmd::class.java.getMethod("getCommand").invoke(cmd) as? String
                ?: return
            val payload = cmd::class.java.getMethod("getPayload").invoke(cmd) as? JsonObject

            Log.d("ElionMDM", "Executando comando: $commandName")
            
            when (commandName) {
                "reboot_device" -> {
                    Log.w("ElionMDM", "Executando REBOOT do dispositivo")
                    policyManager.rebootDevice()
                }
                "wipe_device" -> {
                    Log.w("ElionMDM", "Executando WIPE DATA (factory reset)")
                    policyManager.wipeData(factoryReset = true)
                }
                "lock_device" -> {
                    Log.d("ElionMDM", "Bloqueando dispositivo")
                    policyManager.enforcePasswordQuality()
                }
                "disable_camera" -> {
                    Log.d("ElionMDM", "Desabilitando câmera")
                    policyManager.toggleCamera(false)
                }
                "enable_camera" -> {
                    Log.d("ElionMDM", "Habilitando câmera")
                    policyManager.toggleCamera(true)
                }
                "kiosk_mode" -> {
                    val pkg = payload?.get("package")?.asString ?: ""
                    Log.d("ElionMDM", "Ativando kiosk mode para: $pkg")
                    policyManager.setKioskMode(pkg, pkg.isNotEmpty())
                }
                "apply_policy" -> {
                    Log.d("ElionMDM", "Aplicando política")
                    if (payload != null) {
                        val disableCamera = payload.get("camera_disabled")?.asBoolean ?: false
                        policyManager.toggleCamera(!disableCamera)
                        
                        val kioskMode = payload.get("kiosk_mode")?.asString
                        policyManager.setKioskMode(kioskMode ?: "", !kioskMode.isNullOrEmpty())
                        
                        val resetDisabled = payload.get("factory_reset_disabled")?.asBoolean ?: false
                        if (resetDisabled) {
                            policyManager.enforcePasswordQuality()
                        }
                    }
                }
                else -> {
                    Log.w("ElionMDM", "Comando desconhecido: $commandName")
                }
            }
        } catch (e: Exception) {
            Log.e("ElionMDM", "Erro executando comando: ${e.message}", e)
        }
    }
}
