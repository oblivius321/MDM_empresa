package com.elion.mdm.system

import android.content.Context
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.google.gson.Gson
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.security.MessageDigest
import kotlin.math.pow

/**
 * MDM States — Enterprise 3B
 */
enum class MDMState {
    INIT,           // Estado inicial (fábrica)
    REGISTERING,    // Handshake de identidade (/enroll)
    PROVISIONING,   // Handshake de Bootstrap (SSOT)
    ENFORCING,      // Aplicando políticas determinísticas
    OPERATIONAL,    // Conformidade atingida
    ERROR           // Falha crítica ou Cooldown
}

/**
 * MDMStateMachine — O coração resiliente do Elion MDM.
 *
 * Implementa:
 * - Persistência Segura (SHA-256 Checksum)
 * - Exponential Backoff (retry logic)
 * - Cooldown Anti-Brick (CPU/Bateria protection)
 */
object MDMStateMachine {
    private const val TAG = "ElionStateMachine"
    private const val MAX_RETRIES = 5
    private const val BASE_DELAY_MS = 5000L // 5 segundos base
    
    private val mutex = Mutex()
    private val gson = Gson()
    
    suspend fun transitionTo(context: Context, newState: MDMState, error: String? = null, metadata: Map<String, String>? = null) {
        mutex.withLock {
            val prefs = SecurePreferences(context)
            val currentPayload = prefs.enrollmentStatePayload
            
            // Lógica de Retry/Exponential Backoff
            var retryCount = 0
            var cooldownUntil = 0L
            
            if (newState == MDMState.ERROR) {
                val current = try { 
                   if (currentPayload != null) gson.fromJson(currentPayload, Map::class.java) else emptyMap<String, Any>()
                } catch(e: Exception) { emptyMap<String, Any>() }
                
                retryCount = ((current["retry_count"] as? Double)?.toInt() ?: 0) + 1
                
                if (retryCount >= MAX_RETRIES) {
                    // Triga Cooldown de 30 minutos após 5 falhas
                    cooldownUntil = System.currentTimeMillis() + (30 * 60 * 1000L)
                    Log.w(TAG, "Limite de retentativas atingido ($retryCount). Entrando em COOLDOWN até $cooldownUntil")
                } else {
                    // Backoff Exponencial: 5s, 10s, 20s, 40s, 80s...
                    val delay = (BASE_DELAY_MS * 2.0.pow(retryCount.toDouble())).toLong()
                    cooldownUntil = System.currentTimeMillis() + delay
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
                return@withLock StateInfo(MDMState.ERROR, error = "Corrupção de Estado")
            }
            
            return try {
                val map = gson.fromJson(payload, Map::class.java) as Map<String, Any>
                val state = MDMState.valueOf(map["state"] as String)
                
                StateInfo(
                    state = state,
                    retryCount = (map["retry_count"] as? Double)?.toInt() ?: 0,
                    cooldownUntil = (map["cooldown_until"] as? Double)?.toLong() ?: 0L,
                    lastError = map["last_error"] as? String,
                    @Suppress("UNCHECKED_CAST")
                    metadata = map["metadata"] as? Map<String, String> ?: emptyMap()
                )
            } catch (e: Exception) {
                StateInfo(MDMState.ERROR, error = "Erro ao ler estado: ${e.message}")
            }
        }
    }

    data class StateInfo(
        val state: MDMState,
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
