package com.elion.mdm.domain

import android.content.Context
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.data.repository.DeviceRepository
import com.elion.mdm.data.remote.dto.DeviceHealth
import com.elion.mdm.system.MDMStateMachine

/**
 * ComplianceManager — O guardião da conformidade enterprise.
 *
 * Responsabilidades:
 * 1. Calcular o Hash local da política atual.
 * 2. Comparar com o Hash mestre do Backend.
 * 3. Identificar Drift (desvio) e reportar Health Status.
 * 4. Acionar o PolicyManager para Auto-Healing.
 */
class ComplianceManager(
    private val context: Context,
    private val repository: DeviceRepository,
    private val policyManager: PolicyManager
) {
    private val prefs = SecurePreferences(context)

    companion object {
        private const val TAG = "ElionCompliance"
    }

    /**
     * Executa uma verificação completa de conformidade.
     * Retorna a saúde atual do dispositivo.
     */
    suspend fun checkCompliance(): DeviceHealth {
        val state = MDMStateMachine.getStateInfo(context)
        Log.d(TAG, "Iniciando verificação de conformidade [Híbrida]")

        // 1. Recuperar SSOT do Backend
        val result = repository.bootstrapData()
        
        return result.fold(
            onSuccess = { bootstrap ->
                val localHash = state.metadata["policy_hash"] ?: ""
                
                if (bootstrap.policyHash != localHash) {
                    Log.w(TAG, "Drift detectado! Backend: ${bootstrap.policyHash} | Local: $localHash")
                    handleDrift(bootstrap.policyHash)
                    DeviceHealth.DEGRADED
                } else {
                    Log.i(TAG, "Dispositivo em conformidade total. Policy Hash: $localHash")
                    DeviceHealth.COMPLIANT
                }
            },
            onFailure = {
                Log.e(TAG, "Falha ao validar compliance: ${it.message}")
                DeviceHealth.DEGRADED // Falha de rede = Saúde degradada (não crítica)
            }
        )
    }

    /**
     * Corrige desvios automaticamente.
     */
    private suspend fun handleDrift(newHash: String) {
        MDMStateMachine.transitionTo(
            context, 
            com.elion.mdm.system.MDMState.ENFORCING,
            error = "DRIFT_DETECTED",
            metadata = mapOf("policy_hash" to newHash)
        )
    }
}
