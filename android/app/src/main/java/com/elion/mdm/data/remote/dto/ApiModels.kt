package com.elion.mdm.data.remote.dto

import com.google.gson.annotations.SerializedName

enum class DeviceHealth {
    COMPLIANT,
    DEGRADED,
    NON_COMPLIANT,
    UNKNOWN
}

// ─── Enrollment ───────────────────────────────────────────────────────────────

data class EnrollmentRequest(
    @SerializedName("device_id")        val deviceId: String,
    @SerializedName("name")             val name: String,
    @SerializedName("device_type")       val deviceType: String = "android",
    @SerializedName("bootstrap_token")  val bootstrapToken: String,
    @SerializedName("profile_id")       val profileId: String? = null,
    @SerializedName("device_model")      val deviceModel: String? = null,
    @SerializedName("android_version")   val androidVersion: String? = null,
    @SerializedName("imei")              val imei: String? = null,
    @SerializedName("installed_apps")    val installedApps: List<String>? = null,
    @SerializedName("extra_data")        val extraData: Map<String, String>? = null
)

data class EnrollmentResponse(
    @SerializedName("device_id")    val deviceId: String,
    @SerializedName("device_token") val deviceToken: String,
    @SerializedName("message")      val message: String? = null
)

// ─── Check-in ─────────────────────────────────────────────────────────────────

data class CheckinRequest(
    @SerializedName("battery_level")       val batteryLevel: Int,
    @SerializedName("is_charging")         val isCharging: Boolean = false,
    @SerializedName("device_model")        val deviceModel: String,
    @SerializedName("android_version")     val androidVersion: String,
    @SerializedName("imei")                val imei: String? = null,
    @SerializedName("serial")              val serial: String? = null,
    @SerializedName("compliance_status")   val complianceStatus: String,
    @SerializedName("free_disk_space_mb")  val freeDiskSpaceMb: Int? = null,
    @SerializedName("installed_apps")      val installedApps: List<String>? = null,
    @SerializedName("latitude")            val latitude: Double? = null,
    @SerializedName("longitude")           val longitude: Double? = null,
    @SerializedName("foreground_app")      val foregroundApp: String? = null,
    @SerializedName("timestamp")           val timestamp: Long = System.currentTimeMillis()
)

data class CheckinResponse(
    @SerializedName("status")           val status: String,
    @SerializedName("checkin_interval") val checkinInterval: Int? = null
)

// ─── Commands ─────────────────────────────────────────────────────────────────

data class DeviceCommand(
    @SerializedName(value = "id", alternate = ["command_id"])
    val id: Long,
    @SerializedName(value = "command_type", alternate = ["type", "action"])
    val type: String,
    @SerializedName("payload")
    val payload: Map<String, Any?> = emptyMap(),
    @SerializedName("created_at")
    val createdAt: String? = null
)

data class CommandCompleteRequest(
    @SerializedName("status")
    val status: String,
    @SerializedName(value = "error_message", alternate = ["message"])
    val errorMessage: String? = null
)

// ─── Policy ───────────────────────────────────────────────────────────────────

data class PolicyResponse(
    @SerializedName("camera_disabled")            val cameraDisabled: Boolean = false,
    @SerializedName("status_bar_disabled")        val statusBarDisabled: Boolean = false,
    @SerializedName("kiosk_mode_enabled")         val kioskModeEnabled: Boolean = false,
    @SerializedName("kiosk_package")              val kioskPackage: String? = null,
    @SerializedName("min_password_length")        val minPasswordLength: Int = 6,
    @SerializedName("screen_timeout_seconds")     val screenTimeoutSeconds: Int = 300,
    @SerializedName("checkin_interval_seconds")   val checkinIntervalSeconds: Int = 60
)

// ─── Admin Authentication ─────────────────────────────────────────────────────

data class AdminLoginRequest(
    @SerializedName("email")    val email: String,
    @SerializedName("password") val password: String
)

data class AdminLoginResponse(
    @SerializedName("message") val message: String?,
    @SerializedName("user")    val user: AdminUser?
)

data class AdminUser(
    @SerializedName("email")    val email: String,
    @SerializedName("is_admin") val isAdmin: Boolean,
    @SerializedName("id")       val id: Int
)

// ─── Tipos de comando ─────────────────────────────────────────────────────────

object CommandType {
    const val LOCK               = "LOCK"
    const val WIPE               = "WIPE"
    const val KIOSK_ENABLE       = "KIOSK"
    const val KIOSK_DISABLE      = "KIOSK_DISABLE"
    const val CAMERA_DISABLE     = "DISABLE_CAMERA"
    const val CAMERA_ENABLE      = "ENABLE_CAMERA"
    const val STATUS_BAR_DISABLE = "DISABLE_STATUS_BAR"
    const val STATUS_BAR_ENABLE  = "ENABLE_STATUS_BAR"
    const val INSTALL_APK        = "INSTALL_APK"
    const val INSTALL_APP        = "INSTALL_APP"
    const val REBOOT             = "REBOOT"
    const val SYNC_POLICY        = "SYNC_POLICY"
    const val EXIT_KIOSK         = "EXIT_KIOSK"
    const val ENABLE_KIOSK       = "ENABLE_KIOSK"
    const val DISABLE_KIOSK      = "DISABLE_KIOSK"
}

// ─── State Report ─────────────────────────────────────────────────────────────

data class StateReportRequest(
    @SerializedName("health")           val health: String,
    @SerializedName("reason_code")      val reasonCode: String? = null,
    @SerializedName("policy_hash")      val policyHash: String,
    @SerializedName("applied_policies") val appliedPolicies: List<String> = emptyList(),
    @SerializedName("failed_policies")  val failedPolicies: List<String> = emptyList(),
    @SerializedName("timestamp")        val timestamp: String? = null
)

// ─── Bootstrap (SSOT) ─────────────────────────────────────────────────────────

data class BootstrapResponse(
    @SerializedName("device_id")        val deviceId: String,
    @SerializedName("policy_version")   val policyVersion: Int,
    @SerializedName("policy_hash")      val policyHash: String,
    @SerializedName("config")           val config: Map<String, Any>,
    @SerializedName("kiosk_enabled")    val kioskEnabled: Boolean,
    @SerializedName("allowed_apps")     val allowedApps: List<String>,
    @SerializedName("blocked_features") val blockedFeatures: Map<String, Any>,
    @SerializedName("pending_commands") val pendingCommands: List<DeviceCommand> = emptyList()
)

// ─── Trust & Attestation (Phase 4) ────────────────────────────────────────────

data class NonceResponse(
    @SerializedName("nonce")      val nonce: String,
    @SerializedName("expires_in") val expiresIn: Int
)

data class AttestationRequest(
    @SerializedName("integrity_token") val integrityToken: String,
    @SerializedName("nonce")           val nonce: String
)
