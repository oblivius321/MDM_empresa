package com.elion.mdm.data.repository

import android.content.Context
import android.os.Build
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.data.remote.ApiClient
import com.elion.mdm.data.remote.dto.EnrollmentRequest
import com.elion.mdm.data.remote.dto.EnrollmentResponse

/**
 * DeviceRepository — camada de dados para operações de enrollment e identidade do dispositivo.
 *
 * Segue o Repository Pattern da Clean Architecture:
 *   Presentation → UseCase → Repository → DataSource (Remote/Local)
 *
 * O repositório decide de onde buscar os dados (cache local ou rede),
 * isolando essa decisão das camadas superiores.
 */
class DeviceRepository(private val context: Context) {

    companion object {
        private const val TAG = "ElionDeviceRepo"
    }

    private val prefs = SecurePreferences(context)

    // ─── Enrollment ───────────────────────────────────────────────────────────

    /**
     * Registra o dispositivo no backend com o bootstrap_secret.
     * Em caso de sucesso, persiste device_id e device_token localmente.
     *
     * @param bootstrapSecret chave de bootstrap configurada no servidor
     * @param backendUrl URL do servidor MDM (salva para uso futuro)
     * @return Result com EnrollmentResponse em caso de sucesso
     */
    suspend fun enroll(bootstrapSecret: String, backendUrl: String): Result<EnrollmentResponse> =
        runCatching {
            // Persiste a URL antes de criar o cliente (ApiClient lê das prefs)
            prefs.backendUrl = backendUrl
            ApiClient.invalidate()

            val api     = ApiClient.getInstance(context)
            val request = EnrollmentRequest(
                bootstrapSecret = bootstrapSecret,
                deviceModel     = "${Build.MANUFACTURER} ${Build.MODEL}",
                androidVersion  = Build.VERSION.RELEASE,
                serialNumber    = Build.SERIAL.takeIf { it != Build.UNKNOWN } ?: "UNKNOWN"
            )

            val response = api.enroll(request)

            if (!response.isSuccessful) {
                error("Enrollment falhou: HTTP ${response.code()} — ${response.errorBody()?.string()}")
            }

            val body = response.body() ?: error("Response body vazio")

            // Persiste credenciais de forma segura
            prefs.deviceId    = body.deviceId
            prefs.deviceToken = body.deviceToken
            prefs.isEnrolled  = true

            Log.i(TAG, "Enrollment OK — deviceId=${body.deviceId}")
            body
        }

    // ─── Estado local ─────────────────────────────────────────────────────────

    fun isEnrolled(): Boolean = prefs.hasValidToken()

    fun getDeviceId(): String? = prefs.deviceId

    fun getLastSyncTimestamp(): Long = prefs.lastSyncTimestamp

    fun unenroll() {
        Log.w(TAG, "Unenroll — limpando credenciais locais")
        prefs.clearAll()
        ApiClient.invalidate()
    }
}
