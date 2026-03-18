package com.elion.mdm.data.local

import android.content.Context
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
 * Nunca armazene device_token em SharedPreferences comuns — ele é uma
 * credencial de autenticação do dispositivo no backend.
 */
class SecurePreferences(context: Context) {

    companion object {
        private const val FILE_NAME            = "elion_mdm_secure_prefs"
        private const val KEY_DEVICE_TOKEN     = "device_token"
        private const val KEY_DEVICE_ID        = "device_id"
        private const val KEY_ENROLLED         = "is_enrolled"
        private const val KEY_BACKEND_URL      = "backend_url"
        private const val KEY_CHECKIN_INTERVAL = "checkin_interval_seconds"
        private const val KEY_LAST_SYNC        = "last_sync_timestamp"
        private const val DEFAULT_BACKEND_URL  = "https://mdm.suaempresa.com"
    }

    private val prefs = EncryptedSharedPreferences.create(
        context,
        FILE_NAME,
        MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

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

    fun clearAll() = prefs.edit().clear().apply()

    fun hasValidToken(): Boolean = !deviceToken.isNullOrBlank() && isEnrolled
}
