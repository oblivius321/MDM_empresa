package com.elion.mdm.data.remote.dto

import com.google.gson.annotations.SerializedName

// ─── Enrollment ───────────────────────────────────────────────────────────────

data class EnrollmentRequest(
    @SerializedName("bootstrap_secret") val bootstrapSecret: String,
    @SerializedName("device_model")     val deviceModel: String,
    @SerializedName("android_version")  val androidVersion: String,
    @SerializedName("serial_number")    val serialNumber: String,
    @SerializedName("imei")             val imei: String? = null
)

data class EnrollmentResponse(
    @SerializedName("device_id")    val deviceId: String,
    @SerializedName("device_token") val deviceToken: String,
    @SerializedName("message")      val message: String? = null
)

// ─── Check-in ─────────────────────────────────────────────────────────────────

data class CheckinRequest(
    @SerializedName("device_id")         val deviceId: String,
    @SerializedName("battery_level")     val batteryLevel: Int,
    @SerializedName("device_model")      val deviceModel: String,
    @SerializedName("android_version")   val androidVersion: String,
    @SerializedName("compliance_status") val complianceStatus: String,
    @SerializedName("timestamp")         val timestamp: Long = System.currentTimeMillis()
)

data class CheckinResponse(
    @SerializedName("status")           val status: String,
    @SerializedName("checkin_interval") val checkinInterval: Int? = null
)

// ─── Commands ─────────────────────────────────────────────────────────────────

data class DeviceCommand(
    @SerializedName("id")         val id: Long,
    @SerializedName("type")       val type: String,
    @SerializedName("payload")    val payload: Map<String, String> = emptyMap(),
    @SerializedName("created_at") val createdAt: String? = null
)

data class CommandCompleteRequest(
    @SerializedName("status")  val status: String,
    @SerializedName("message") val message: String? = null
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
    const val REBOOT             = "REBOOT"
    const val SYNC_POLICY        = "SYNC_POLICY"
}
