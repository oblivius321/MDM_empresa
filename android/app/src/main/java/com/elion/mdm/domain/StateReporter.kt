package com.elion.mdm.domain

import android.content.Context
import android.os.BatteryManager
import android.os.SystemClock
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.data.remote.ApiClient
import com.elion.mdm.data.remote.dto.StateReportRequest
import com.elion.mdm.system.LocalLogger
import com.elion.mdm.domain.utils.NetworkUtils
import com.google.gson.GsonBuilder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.security.MessageDigest
import java.util.TreeMap

class StateReporter(private val context: Context) {

    companion object {
        private const val TAG = "ElionStateReporter"
        private val reportMutex = Mutex()
        private const val THROTTLE_MS = 10 * 60 * 1000L // 10 minutos
    }

    private val dpm = DevicePolicyHelper(context)
    private val prefs = SecurePreferences(context)
    private val api = ApiClient.getInstance(context)

    suspend fun reportState() = withContext(Dispatchers.IO) {
        val deviceId = prefs.deviceId ?: return@withContext

        reportMutex.withLock {
            val stateMap = collectDeviceState()
            val stateHash = canonicalizeAndHash(stateMap)
            
            val now = SystemClock.elapsedRealtime()
            val timeSinceLastReport = now - prefs.lastStateReportMs
            
            // Throttling Logic: Send if hash changed, or 10 min elapsed, or first time
            val hashChanged = stateHash != prefs.lastStateHash
            val heartbeatExpired = timeSinceLastReport >= THROTTLE_MS
            val isFirstTime = prefs.lastStateHash == null
            
            if (!hashChanged && !heartbeatExpired && !isFirstTime) {
                Log.d(TAG, "Throttled: Estado não mudou e heartbeat não expirou. Ignorando envio.")
                return@withLock
            }

            val request = StateReportRequest(
                health = if (dpm.isDeviceOwner()) "COMPLIANT" else "DEGRADED",
                reasonCode = "STATE_REPORT",
                policyHash = stateHash
            )

            try {
                Log.d(TAG, "Enviando State Report. Hash: $stateHash")
                
                // Retry com backoff exponencial
                NetworkUtils.retryWithBackoff(times = 3) {
                    val response = api.reportStatus(deviceId, request)
                    if (response.isSuccessful) {
                        prefs.lastStateHash = stateHash
                        prefs.lastStateReportMs = now
                        Log.i(TAG, "State Report enviado com sucesso.")
                    } else {
                        throw Exception("HTTP ${response.code()}")
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Falha ao enviar State Report: ${e.message}")
                LocalLogger.log(context, "STATE_REPORT_FAILED", "Falha após retries: ${e.message}")

                // Fallback para Store & Forward Offline Queue
                val gson = com.google.gson.Gson()
                val payloadObj = gson.toJsonTree(request).asJsonObject
                com.elion.mdm.system.OfflineQueue.enqueue(context, com.elion.mdm.system.QueuedEvent(
                    type = com.elion.mdm.system.OfflineQueue.TYPE_STATE,
                    priority = com.elion.mdm.system.OfflineQueue.PRIO_STATE,
                    payload = payloadObj,
                    timestamp = System.currentTimeMillis(),
                    deviceId = deviceId
                ))
            }
        }
    }

    private fun collectDeviceState(): Map<String, Any> {
        val restrictions = mapOf(
            "camera_disabled" to dpm.isCameraDisabled(),
            "kiosk_active" to dpm.isInLockTaskMode()
        )

        val kioskPackages = dpm.getKioskPackages().toList().sorted()

        val batteryStatus: android.content.Intent? = android.content.IntentFilter(android.content.Intent.ACTION_BATTERY_CHANGED).let { ifilter ->
            context.registerReceiver(null, ifilter)
        }
        val batteryPct: Int = batteryStatus?.let { intent ->
            val level: Int = intent.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL, -1)
            val scale: Int = intent.getIntExtra(android.os.BatteryManager.EXTRA_SCALE, -1)
            (level * 100 / scale.toFloat()).toInt()
        } ?: -1
        val isCharging: Boolean = batteryStatus?.let { intent ->
            val status: Int = intent.getIntExtra(android.os.BatteryManager.EXTRA_STATUS, -1)
            status == android.os.BatteryManager.BATTERY_STATUS_CHARGING || status == android.os.BatteryManager.BATTERY_STATUS_FULL
        } ?: false

        val telemetry = mutableMapOf<String, Any>(
            "uptime_ms" to SystemClock.elapsedRealtime(),
            "last_ws_connected_at" to prefs.lastWsConnectedAt,
            "queue_size" to prefs.queueSize,
            "last_flush_ts" to prefs.lastFlushTs,
            "battery" to batteryPct,
            "charging" to isCharging,
            "network" to NetworkUtils.getNetworkType(context),
            "android_patch" to android.os.Build.VERSION.SECURITY_PATCH,
            "app_version" to com.elion.mdm.BuildConfig.VERSION_NAME,
            "kiosk_active" to prefs.isKioskEnabled,
            "apps_installed" to kioskPackages.size, // Pacotes atualmente filtrados pra o Lockdown App do Launcher
            "apps_expected" to kioskPackages.size
        )

        val currentReconnectCount = prefs.wsReconnectCount
        val currentErrorCode = prefs.lastErrorCode ?: ""

        if (currentReconnectCount != prefs.lastReportedReconnectCount || currentErrorCode != prefs.lastReportedErrorCode) {
            telemetry["ws_reconnect_count"] = currentReconnectCount
            telemetry["last_error_code"] = currentErrorCode
            
            prefs.lastReportedReconnectCount = currentReconnectCount
            prefs.lastReportedErrorCode = currentErrorCode
        }

        return mapOf(
            "restrictions" to restrictions,
            "kiosk_packages" to kioskPackages,
            "battery" to getBatteryLevel(),
            "telemetry" to telemetry
        )
    }

    private fun getBatteryLevel(): Int {
        val bm = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        return bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
    }

    private fun canonicalizeAndHash(stateMap: Map<String, Any>): String {
        val sortedMap = sortMapRecursively(stateMap)
        val gson = GsonBuilder().create()
        val jsonString = gson.toJson(sortedMap)
        
        val digest = MessageDigest.getInstance("SHA-256")
            .digest(jsonString.toByteArray(Charsets.UTF_8))
            
        return digest.joinToString("") { "%02x".format(it) }
    }

    private fun sortMapRecursively(map: Map<String, Any>): TreeMap<String, Any> {
        val sorted = TreeMap<String, Any>()
        for ((k, v) in map) {
            if (v is Map<*, *>) {
                @Suppress("UNCHECKED_CAST")
                sorted[k] = sortMapRecursively(v as Map<String, Any>)
            } else if (v is List<*>) {
                // Presumimos listas de strings para ordenação simples
                sorted[k] = v.map { it.toString() }.sorted()
            } else {
                sorted[k] = v
            }
        }
        return sorted
    }
}
