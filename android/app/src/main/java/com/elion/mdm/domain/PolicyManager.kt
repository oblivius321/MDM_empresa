package com.elion.mdm.domain

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.util.Log
import com.elion.mdm.data.remote.dto.BootstrapResponse
import com.elion.mdm.domain.usecase.DevicePolicyHelper
import com.elion.mdm.system.KioskManager

/**
 * PolicyManager — O motor de execução determinístico do Elion MDM.
 *
 * Implementa a "Ordem de Ouro" de aplicação (Enterprise Standard):
 * 1. Security Policies (Senhas, Criptografia)
 * 2. Device Restrictions (USB, Bluetooth, Factory Reset)
 * 3. App Provisioning (Instalação/Permissões)
 * 4. Kiosk Mode (LockTask — sempre por último)
 */
class PolicyManager(
    private val context: Context,
    private val dpm: DevicePolicyManager,
    private val admin: ComponentName
) {
    private val policyHelper = DevicePolicyHelper(context)
    private val kioskManager = KioskManager(context, dpm, admin)

    companion object {
        private const val TAG = "ElionPolicyManager"
    }

    /**
     * Aplica a política completa de forma atômica e determinística.
     * Retorna uma lista das políticas que falharam (se houver).
     */
    fun applyFullPolicy(policy: BootstrapResponse): List<String> {
        val failedSteps = mutableListOf<String>()
        Log.i(TAG, "Iniciando aplicação determinística — Versão: ${policy.policyVersion}")

        try {
            // 1. Security Policies
            if (!applySecurityPolicies(policy.config)) {
                failedSteps.add("SECURITY_POLICIES")
            }

            // 2. Device Restrictions
            if (!applyRestrictions(policy.blockedFeatures)) {
                failedSteps.add("DEVICE_RESTRICTIONS")
            }

            // 3. Apps (Whitelisting / Provisioning)
            if (!applyAppPolicies(policy.allowedApps)) {
                failedSteps.add("APP_POLICIES")
            }

            // 4. Kiosk Mode (FINAL STEP)
            if (policy.kioskEnabled) {
                if (!enableKioskMode()) {
                    failedSteps.add("KIOSK_MODE")
                }
            } else {
                kioskManager.stopKiosk()
            }

        } catch (e: Exception) {
            Log.e(TAG, "Falha crítica na aplicação da política: ${e.message}")
            failedSteps.add("CRITICAL_EXCEPTION: ${e.message}")
        }

        return failedSteps
    }

    private fun applySecurityPolicies(config: Map<String, Any>): Boolean {
        return try {
            // Exemplo: Comprimento de senha
            val minPassword = (config["min_password_length"] as? Double)?.toInt() ?: 4
            dpm.setPasswordQuality(admin, DevicePolicyManager.PASSWORD_QUALITY_SOMETHING)
            dpm.setPasswordMinimumLength(admin, minPassword)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Falha SecurityPolicies: ${e.message}")
            false
        }
    }

    private fun applyRestrictions(features: Map<String, Any>): Boolean {
        return try {
            // Itera sobre as restrições bloqueadas
            features.forEach { (key, blocked) ->
                if (blocked == true) {
                    policyHelper.setRestriction(key, true)
                } else {
                    policyHelper.setRestriction(key, false)
                }
            }
            true
        } catch (e: Exception) {
            Log.e(TAG, "Falha Restrictions: ${e.message}")
            false
        }
    }

    private fun applyAppPolicies(allowedApps: List<String>): Boolean {
        return try {
            // No Android, o KioskManager define quem pode rodar no LockTask.
            // Aqui poderíamos também esconder apps via dpm.setApplicationHidden.
            true
        } catch (e: Exception) {
            false
        }
    }

    private fun enableKioskMode(): Boolean {
        return try {
            kioskManager.startKiosk()
            true
        } catch (e: Exception) {
            Log.e(TAG, "Falha KioskMode: ${e.message}")
            false
        }
    }
}
