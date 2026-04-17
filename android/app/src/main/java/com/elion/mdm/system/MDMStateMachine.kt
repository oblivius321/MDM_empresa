package com.elion.mdm.system

import android.content.Context
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.google.gson.Gson
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.security.MessageDigest
import kotlin.math.pow

enum class MDMState {
    INIT,
    REGISTERING,
    PROVISIONING,
    ENFORCING,
    OPERATIONAL,
    ERROR
}

object MDMStateMachine {
    private const val TAG = "ElionStateMachine"
    private const val MAX_RETRIES = 5
    private const val BASE_DELAY_MS = 5000L

    private val mutex = Mutex()
    private val gson = Gson()

    suspend fun transitionTo(
        context: Context,
        newState: MDMState,
        error: String? = null,
        metadata: Map<String, String>? = null
    ) {
        mutex.withLock {
            val prefs = SecurePreferences(context)
            val currentPayload = prefs.enrollmentStatePayload

            var retryCount = 0
            var cooldownUntil = 0L

            if (newState == MDMState.ERROR) {
                val current = try {
                    if (currentPayload != null) gson.fromJson(currentPayload, Map::class.java) else emptyMap<String, Any>()
                } catch (_: Exception) {
                    emptyMap<String, Any>()
                }

                retryCount = ((current["retry_count"] as? Double)?.toInt() ?: 0) + 1
                cooldownUntil = if (retryCount >= MAX_RETRIES) {
                    System.currentTimeMillis() + (30 * 60 * 1000L)
                } else {
                    val delay = (BASE_DELAY_MS * 2.0.pow(retryCount.toDouble())).toLong()
                    System.currentTimeMillis() + delay
                }
            }

            val stateData = mutableMapOf(
                "state" to newState.name,
                "timestamp" to System.currentTimeMillis(),
                "retry_count" to retryCount,
                "cooldown_until" to cooldownUntil,
                "last_error" to (error ?: ""),
                "metadata" to (metadata ?: emptyMap<String, String>())
            )

            val jsonPayload = gson.toJson(stateData)
            val checksum = computeChecksum(jsonPayload)

            Log.i(TAG, "State Transition: $newState (Retry: $retryCount, NextAttempt: $cooldownUntil)")

            prefs.enrollmentStatePayload = jsonPayload
            prefs.enrollmentStateChecksum = checksum
        }
    }

    suspend fun getStateInfo(context: Context): StateInfo {
        return mutex.withLock {
            val prefs = SecurePreferences(context)
            val payload = prefs.enrollmentStatePayload
            val checksum = prefs.enrollmentStateChecksum

            if (payload == null || checksum == null) {
                return@withLock StateInfo(MDMState.INIT)
            }

            if (computeChecksum(payload) != checksum) {
                return@withLock StateInfo(MDMState.ERROR, lastError = "state_checksum_mismatch")
            }

            return@withLock try {
                val map = gson.fromJson(payload, Map::class.java) as Map<String, Any>
                val stateName = map["state"] as String
                val state = when (stateName) {
                    "BOOTSTRAPPED", "ENROLLING" -> MDMState.REGISTERING
                    "ENROLLED", "SYNCING_POLICIES" -> MDMState.PROVISIONING
                    "KIOSK_APPLIED" -> MDMState.ENFORCING
                    "ERROR_RECOVERY" -> MDMState.ERROR
                    else -> MDMState.valueOf(stateName)
                }
                val metadata = (map["metadata"] as? Map<*, *>)
                    ?.mapNotNull { (key, value) ->
                        key?.toString()?.let { it to (value?.toString() ?: "") }
                    }
                    ?.toMap()
                    ?: emptyMap()

                StateInfo(
                    state = state,
                    timestamp = (map["timestamp"] as? Double)?.toLong() ?: 0L,
                    retryCount = (map["retry_count"] as? Double)?.toInt() ?: 0,
                    cooldownUntil = (map["cooldown_until"] as? Double)?.toLong() ?: 0L,
                    lastError = map["last_error"] as? String,
                    metadata = metadata
                )
            } catch (e: Exception) {
                StateInfo(MDMState.ERROR, lastError = "state_parse_error: ${e.message}")
            }
        }
    }

    data class StateInfo(
        val state: MDMState,
        val timestamp: Long = 0L,
        val retryCount: Int = 0,
        val cooldownUntil: Long = 0L,
        val lastError: String? = null,
        val metadata: Map<String, String> = emptyMap()
    ) {
        fun isInCooldown(): Boolean = System.currentTimeMillis() < cooldownUntil
    }

    private fun computeChecksum(data: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val hash = digest.digest(data.toByteArray(Charsets.UTF_8))
        return hash.joinToString("") { "%02x".format(it) }
    }
}
