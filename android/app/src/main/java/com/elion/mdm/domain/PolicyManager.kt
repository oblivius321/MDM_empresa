package com.elion.mdm.domain

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.data.remote.dto.BootstrapResponse
import com.elion.mdm.system.DevMode
import com.elion.mdm.system.KioskManager
import org.json.JSONArray

class PolicyManager(
    private val context: Context,
    private val dpm: DevicePolicyManager,
    private val admin: ComponentName
) {
    private val policyHelper = DevicePolicyHelper(context)
    private val kioskManager = KioskManager(context)
    private val prefs = SecurePreferences(context)

    companion object {
        private const val TAG = "ElionPolicyManager"
    }

    fun applyFullPolicy(policy: BootstrapResponse): List<String> {
        val failedSteps = mutableListOf<String>()
        Log.i(TAG, "Aplicando politica version=${policy.policyVersion}, kiosk=${policy.kioskEnabled}")
        val effectiveAllowedApps = resolveAllowedApps(policy.allowedApps, policy.config)

        try {
            if (!applySecurityPolicies(policy.config)) {
                failedSteps.add("SECURITY_POLICIES")
            }

            if (!applyRestrictions(policy.blockedFeatures)) {
                failedSteps.add("DEVICE_RESTRICTIONS")
            }

            if (!applyAppPolicies(effectiveAllowedApps, policy.config)) {
                failedSteps.add("APP_POLICIES")
            }

            if (policy.kioskEnabled) {
                if (!enableKioskMode(effectiveAllowedApps)) {
                    failedSteps.add("KIOSK_MODE")
                }
            } else {
                kioskManager.disableKiosk()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Falha critica na aplicacao da politica: ${e.message}")
            failedSteps.add("CRITICAL_EXCEPTION: ${e.message}")
        }

        return failedSteps
    }

    private fun applySecurityPolicies(config: Map<String, Any>): Boolean {
        return try {
            val settings = (config["config"] as? Map<*, *>) ?: emptyMap<String, Any>()
            val passwordRequirements = (config["password_requirements"] as? Map<*, *>) ?: emptyMap<String, Any>()
            val minPassword = numberValue(settings["min_password_length"])
                ?: numberValue(passwordRequirements["min_password_length"])
                ?: numberValue(passwordRequirements["min_length"])
                ?: numberValue(config["min_password_length"])
                ?: 4
            DevMode.applyPolicySafe("password quality/minimum length") {
                dpm.setPasswordQuality(admin, DevicePolicyManager.PASSWORD_QUALITY_SOMETHING)
                dpm.setPasswordMinimumLength(admin, minPassword)
            }

            val screenTimeoutSeconds = numberValue(settings["screen_timeout_seconds"])
                ?: numberValue(config["screen_timeout_seconds"])
            if (screenTimeoutSeconds != null && screenTimeoutSeconds > 0) {
                policyHelper.setScreenOffTimeout(screenTimeoutSeconds * 1000L)
            }

            val checkinSeconds = numberValue(settings["checkin_interval_seconds"])
            val checkinMinutes = numberValue(settings["checkin_interval_minutes"])
            val intervalSeconds = checkinSeconds ?: checkinMinutes?.times(60)
            if (intervalSeconds != null && intervalSeconds > 0) {
                prefs.checkinIntervalSeconds = intervalSeconds
            }

            true
        } catch (e: Exception) {
            Log.e(TAG, "Falha SecurityPolicies: ${e.message}")
            false
        }
    }

    private fun applyRestrictions(features: Map<String, Any>): Boolean {
        return try {
            features.forEach { (key, blocked) ->
                policyHelper.setRestriction(key, blocked == true)
            }
            true
        } catch (e: Exception) {
            Log.e(TAG, "Falha Restrictions: ${e.message}")
            false
        }
    }

    private fun applyAppPolicies(allowedApps: List<String>, config: Map<String, Any>): Boolean {
        return try {
            val array = JSONArray()
            allowedApps.distinct().forEach { array.put(it) }
            prefs.allowedAppsJson = array.toString()
            prefs.kioskTargetPackage = readKioskTargetPackage(config)

            val blockedApps = stringList(config["blocked_apps"]).distinct()
            val previousBlockedApps = try {
                val previous = JSONArray(prefs.blockedAppsJson)
                (0 until previous.length()).map { previous.getString(it) }
            } catch (_: Exception) {
                emptyList()
            }

            (previousBlockedApps - blockedApps.toSet()).forEach { packageName ->
                policyHelper.setApplicationHidden(packageName, false)
            }
            blockedApps.forEach { packageName ->
                policyHelper.setApplicationHidden(packageName, true)
            }

            val blockedArray = JSONArray()
            blockedApps.forEach { blockedArray.put(it) }
            prefs.blockedAppsJson = blockedArray.toString()

            true
        } catch (e: Exception) {
            Log.e(TAG, "Falha AppPolicies: ${e.message}")
            false
        }
    }

    private fun resolveAllowedApps(
        allowedApps: List<String>,
        config: Map<String, Any>
    ): List<String> {
        val targetPackage = readKioskTargetPackage(config)
        val merged = allowedApps
            .map { it.trim() }
            .filter { it.isNotBlank() }
            .toMutableList()

        if (!targetPackage.isNullOrBlank() && !merged.contains(targetPackage)) {
            merged.add(targetPackage)
        }

        return merged.distinct()
    }

    private fun enableKioskMode(allowedApps: List<String>): Boolean {
        return try {
            kioskManager.enableKiosk(allowedApps)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Falha KioskMode: ${e.message}")
            false
        }
    }

    private fun numberValue(value: Any?): Int? {
        return when (value) {
            is Number -> value.toInt()
            is String -> value.toIntOrNull()
            else -> null
        }
    }

    private fun stringList(value: Any?): List<String> {
        return when (value) {
            is List<*> -> value.mapNotNull { it as? String }.filter { it.isNotBlank() }
            is Array<*> -> value.mapNotNull { it as? String }.filter { it.isNotBlank() }
            else -> emptyList()
        }
    }

    private fun readKioskTargetPackage(config: Map<String, Any>): String? {
        val kiosk = config["kiosk"] as? Map<*, *>
        val settings = config["config"] as? Map<*, *>

        return listOfNotNull(
            kiosk?.get("package_name"),
            kiosk?.get("package"),
            config["kiosk_package"],
            settings?.get("kiosk_package")
        ).firstNotNullOfOrNull { value ->
            value?.toString()?.trim()?.takeIf { it.isNotBlank() }
        }
    }
}
