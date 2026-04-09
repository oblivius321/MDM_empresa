package com.elion.mdm.system

import android.content.Context
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.google.gson.Gson
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.security.MessageDigest

enum class EnrollmentState {
    INIT,
    BOOTSTRAPPED,
    ENROLLING,
    ENROLLED,
    SYNCING_POLICIES,
    KIOSK_APPLIED,
    OPERATIONAL,
    ERROR_RECOVERY
}

object EnrollmentStateMachine {
    private const val TAG = "ElionStateMachine"
    private val mutex = Mutex()
    private val gson = Gson()
    
    suspend fun transitionTo(context: Context, newState: EnrollmentState, metadata: Map<String, String>? = null) {
        mutex.withLock {
            val prefs = SecurePreferences(context)
            
            val stateData = mapOf(
                "state" to newState.name,
                "timestamp" to System.currentTimeMillis().toString(),
                "metadata" to (metadata ?: emptyMap())
            )
            
            val jsonPayload = gson.toJson(stateData)
            val checksum = computeChecksum(jsonPayload)
            
            Log.i(TAG, "Transitioning State to: $newState (Checksum: $checksum)")
            
            // Força a escrita de commit instantâneo protegendo o estado anti-desligamento
            prefs.enrollmentStatePayload = jsonPayload
            prefs.enrollmentStateChecksum = checksum
        }
    }
    
    suspend fun getCurrentState(context: Context): Pair<EnrollmentState, Map<String, String>> {
        return mutex.withLock {
            val prefs = SecurePreferences(context)
            val payload = prefs.enrollmentStatePayload
            val checksum = prefs.enrollmentStateChecksum
            
            if (payload == null || checksum == null) {
                return@withLock Pair(EnrollmentState.INIT, emptyMap())
            }
            
            val calculated = computeChecksum(payload)
            if (calculated != checksum) {
                Log.e(TAG, "FATAL CORRUPTION: State checksum mismatch! Reverting to ERROR_RECOVERY")
                return@withLock Pair(EnrollmentState.ERROR_RECOVERY, mapOf("error" to "checksum_mismatch"))
            }
            
            try {
                val map = gson.fromJson(payload, Map::class.java) as Map<String, Any>
                val stateName = map["state"] as? String ?: EnrollmentState.INIT.name
                
                @Suppress("UNCHECKED_CAST")
                val metadata = map["metadata"] as? Map<String, String> ?: emptyMap()
                
                Pair(EnrollmentState.valueOf(stateName), metadata)
            } catch (e: Exception) {
                Log.e(TAG, "FATAL CORRUPTION: State JSON invalid! Reverting to ERROR_RECOVERY. ${e.message}")
                Pair(EnrollmentState.ERROR_RECOVERY, mapOf("error" to "json_parse_error", "details" to (e.message ?: "")))
            }
        }
    }
    
    private fun computeChecksum(data: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val hash = digest.digest(data.toByteArray(Charsets.UTF_8))
        return hash.joinToString("") { "%02x".format(it) }
    }
}
