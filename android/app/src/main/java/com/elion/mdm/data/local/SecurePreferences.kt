package com.elion.mdm.data.local

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * SecurePreferences — wrapper sobre EncryptedSharedPreferences (Jetpack Security).
 *
 * Cifração em repouso:
 *   • Chaves  → AES-256-SIV
 *   • Valores → AES-256-GCM
 *
 * A MasterKey fica no Android Keystore (hardware-backed quando disponível).
 */
class SecurePreferences(context: Context) {

    companion object {
        private const val TAG                  = "ElionSecurePrefs"
        private const val FILE_NAME            = "elion_mdm_secure_prefs"

        // ─── MDM Agent Keys ──────────────────────────────────────────
        private const val KEY_DEVICE_TOKEN     = "device_token"
        private const val KEY_DEVICE_ID        = "device_id"
        private const val KEY_ENROLLED         = "is_enrolled"
        private const val KEY_BACKEND_URL      = "backend_url"
        private const val KEY_CHECKIN_INTERVAL = "checkin_interval_seconds"
        private const val KEY_LAST_SYNC        = "last_sync_timestamp"
        private const val KEY_MDM_STATE        = "mdm_state_enum"
        private const val DEFAULT_BACKEND_URL  = "" // Em branco por segurança/flexibilidade

        // ─── Kiosk Keys ─────────────────────────────────────────────
        private const val KEY_KIOSK_ENABLED       = "kiosk_enabled"
        private const val KEY_ALLOWED_APPS        = "kiosk_allowed_apps"       // JSON array
        private const val KEY_BLOCKED_APPS        = "kiosk_blocked_apps"       // JSON array
        private const val KEY_KIOSK_TARGET_PACKAGE = "kiosk_target_package"
        private const val KEY_ADMIN_PASSWORD_HASH = "admin_password_hash"      // bcrypt hash
        private const val KEY_ADMIN_EMAIL         = "admin_email"
        private const val KEY_LOGIN_ATTEMPTS      = "login_attempts"
        private const val KEY_LOCKOUT_UNTIL        = "lockout_until_ms"
        private const val KEY_SESSION_TOKEN        = "admin_session_token"
        private const val KEY_SESSION_EXPIRY       = "admin_session_expiry_ms"
    }

    private val prefs: SharedPreferences = createEncryptedPreferences(context.applicationContext)

    private fun createEncryptedPreferences(context: Context): SharedPreferences {
        return runCatching {
            buildValidatedEncryptedPreferences(context)
        }.getOrElse { firstError ->
            Log.w(TAG, "SecurePreferences corrompidas; recriando storage local.", firstError)
            context.deleteSharedPreferences(FILE_NAME)
            buildValidatedEncryptedPreferences(context)
        }
    }

    private fun buildValidatedEncryptedPreferences(context: Context): SharedPreferences {
        return buildEncryptedPreferences(context).also { encryptedPrefs ->
            encryptedPrefs.all
        }
    }

    private fun buildEncryptedPreferences(context: Context): SharedPreferences {
        return EncryptedSharedPreferences.create(
            context,
            FILE_NAME,
            MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build(),
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    // ─── MDM Agent ────────────────────────────────────────────────────────────

    var deviceToken: String?
        get() = prefs.getString(KEY_DEVICE_TOKEN, null)
        set(v) = prefs.edit().putString(KEY_DEVICE_TOKEN, v).apply()

    var deviceId: String?
        get() = prefs.getString(KEY_DEVICE_ID, null)
        set(v) = prefs.edit().putString(KEY_DEVICE_ID, v).apply()

    var isEnrolled: Boolean
        get() = prefs.getBoolean(KEY_ENROLLED, false)
        set(v) = prefs.edit().putBoolean(KEY_ENROLLED, v).apply()

    var backendUrl: String
        get() = prefs.getString(KEY_BACKEND_URL, DEFAULT_BACKEND_URL) ?: DEFAULT_BACKEND_URL
        set(v) = prefs.edit().putString(KEY_BACKEND_URL, v).apply()

    var checkinIntervalSeconds: Int
        get() = prefs.getInt(KEY_CHECKIN_INTERVAL, 60)
        set(v) = prefs.edit().putInt(KEY_CHECKIN_INTERVAL, v).apply()

    var lastSyncTimestamp: Long
        get() = prefs.getLong(KEY_LAST_SYNC, 0L)
        set(v) = prefs.edit().putLong(KEY_LAST_SYNC, v).apply()

    var lastStateHash: String?
        get() = prefs.getString("last_state_hash", null)
        set(v) = prefs.edit().putString("last_state_hash", v).apply()
        
    var lastStateReportMs: Long
        get() = prefs.getLong("last_state_report_ms", 0L)
        set(v) = prefs.edit().putLong("last_state_report_ms", v).apply()

    // ─── Telemetria ───────────────────────────────────────────────────────────

    var lastWsConnectedAt: Long
        get() = prefs.getLong("last_ws_connected_at", 0L)
        set(v) = prefs.edit().putLong("last_ws_connected_at", v).apply()

    var wsReconnectCount: Int
        get() = prefs.getInt("ws_reconnect_count", 0)
        set(v) = prefs.edit().putInt("ws_reconnect_count", v).apply()

    var lastErrorCode: String?
        get() = prefs.getString("last_error_code", null)
        set(v) = prefs.edit().putString("last_error_code", v).apply()

    var lastFlushTs: Long
        get() = prefs.getLong("last_flush_ts", 0L)
        set(v) = prefs.edit().putLong("last_flush_ts", v).apply()

    var queueSize: Int
        get() = prefs.getInt("queue_size", 0)
        set(v) = prefs.edit().putInt("queue_size", v).apply()

    var lastReportedReconnectCount: Int
        get() = prefs.getInt("last_rep_reconn_count", -1)
        set(v) = prefs.edit().putInt("last_rep_reconn_count", v).apply()

    var lastReportedErrorCode: String?
        get() = prefs.getString("last_rep_err_code", null)
        set(v) = prefs.edit().putString("last_rep_err_code", v).apply()

    // ─── MDM Lifecycle State ──────────────────────────────────────────────────
    
    var mdmState: com.elion.mdm.domain.MdmState
        get() {
            val name = prefs.getString(KEY_MDM_STATE, com.elion.mdm.domain.MdmState.UNCONFIGURED.name)
            return try {
                com.elion.mdm.domain.MdmState.valueOf(name ?: com.elion.mdm.domain.MdmState.UNCONFIGURED.name)
            } catch (e: Exception) {
                com.elion.mdm.domain.MdmState.UNCONFIGURED
            }
        }
        set(v) = prefs.edit().putString(KEY_MDM_STATE, v.name).apply()

    // ─── Enrollment State Machine ──────────────────────────────────────────
    var enrollmentStatePayload: String?
        get() = prefs.getString("enrollment_state_payload", null)
        set(v) = prefs.edit().putString("enrollment_state_payload", v).apply()
        
    var enrollmentStateChecksum: String?
        get() = prefs.getString("enrollment_state_checksum", null)
        set(v) = prefs.edit().putString("enrollment_state_checksum", v).apply()

    // ─── Kiosk ────────────────────────────────────────────────────────────────

    var isKioskEnabled: Boolean
        get() = prefs.getBoolean(KEY_KIOSK_ENABLED, false)
        set(v) = prefs.edit().putBoolean(KEY_KIOSK_ENABLED, v).apply()

    /** JSON array of package names, e.g. ["com.app1","com.app2"] */
    var allowedAppsJson: String
        get() = prefs.getString(KEY_ALLOWED_APPS, "[]") ?: "[]"
        set(v) = prefs.edit().putString(KEY_ALLOWED_APPS, v).apply()

    var blockedAppsJson: String
        get() = prefs.getString(KEY_BLOCKED_APPS, "[]") ?: "[]"
        set(v) = prefs.edit().putString(KEY_BLOCKED_APPS, v).apply()

    var kioskTargetPackage: String?
        get() = prefs.getString(KEY_KIOSK_TARGET_PACKAGE, null)
        set(v) = prefs.edit().putString(KEY_KIOSK_TARGET_PACKAGE, v).apply()

    var adminPasswordHash: String?
        get() = prefs.getString(KEY_ADMIN_PASSWORD_HASH, null)
        set(v) = prefs.edit().putString(KEY_ADMIN_PASSWORD_HASH, v).apply()

    var adminEmail: String?
        get() = prefs.getString(KEY_ADMIN_EMAIL, null)
        set(v) = prefs.edit().putString(KEY_ADMIN_EMAIL, v).apply()

    var loginAttempts: Int
        get() = prefs.getInt(KEY_LOGIN_ATTEMPTS, 0)
        set(v) = prefs.edit().putInt(KEY_LOGIN_ATTEMPTS, v).apply()

    var lockoutUntilMs: Long
        get() = prefs.getLong(KEY_LOCKOUT_UNTIL, 0L)
        set(v) = prefs.edit().putLong(KEY_LOCKOUT_UNTIL, v).apply()

    var sessionToken: String?
        get() = prefs.getString(KEY_SESSION_TOKEN, null)
        set(v) = prefs.edit().putString(KEY_SESSION_TOKEN, v).apply()

    var sessionExpiryMs: Long
        get() = prefs.getLong(KEY_SESSION_EXPIRY, 0L)
        set(v) = prefs.edit().putLong(KEY_SESSION_EXPIRY, v).apply()

    // ─── Helpers ──────────────────────────────────────────────────────────────

    fun clearAll() = prefs.edit().clear().apply()

    fun hasValidToken(): Boolean = !deviceToken.isNullOrBlank() && isEnrolled

    fun isSessionValid(): Boolean {
        val token = sessionToken
        val expiry = sessionExpiryMs
        return !token.isNullOrBlank() && System.currentTimeMillis() < expiry
    }

    fun clearSession() {
        sessionToken = null
        sessionExpiryMs = 0L
    }

    fun resetLoginAttempts() {
        loginAttempts = 0
        lockoutUntilMs = 0L
    }
}
