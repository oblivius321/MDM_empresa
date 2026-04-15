package com.elion.mdm.data.repository

import android.content.Context
import android.os.Build
import android.provider.Settings
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
            prefs.backendUrl = ApiClient.normalizeRootUrl(backendUrl)
            ApiClient.invalidate()

            val deviceId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID) ?: "UNKNOWN_${System.currentTimeMillis()}"
            val profileId = try {
                prefs.enrollmentStatePayload?.let { json ->
                    val map = com.google.gson.Gson().fromJson(json, Map::class.java) as Map<String, Any>
                    (map["metadata"] as? Map<String, String>)?.get("profile_id")
                }
            } catch (e: Exception) { null }

            val api     = ApiClient.getInstance(context)
            val request = EnrollmentRequest(
                deviceId        = deviceId,
                name            = "${Build.MANUFACTURER} ${Build.MODEL}",
                deviceType      = "android",
                bootstrapSecret = bootstrapSecret,
                extraData       = mapOf(
                    "profile_id" to (profileId ?: ""),
                    "android_version" to Build.VERSION.RELEASE,
                    "legacy_serial"   to (Build.SERIAL.takeIf { it != Build.UNKNOWN } ?: "UNKNOWN")
                )
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

    /**
     * Recupera o estado mestre (SSOT) do dispositivo.
     * Deve ser chamado logo após o enrollment e em cada reentrada crítica.
     */
    suspend fun bootstrapData(): Result<com.elion.mdm.data.remote.dto.BootstrapResponse> =
        runCatching {
            val deviceId = getDeviceId() ?: error("Device ID não encontrado")
            val api = ApiClient.getInstance(context)
            val response = api.getBootstrapData(deviceId)
            
            if (!response.isSuccessful) {
                error("Falha ao obter bootstrap: HTTP ${response.code()}")
            }
            
            response.body() ?: error("Bootstrap body vazio")
        }

    /**
     * Reporta o status de saúde e conformidade (Enterprise 3B).
     */
    suspend fun reportStatus(
        health: com.elion.mdm.data.remote.dto.DeviceHealth,
        reason: String? = null,
        policyHash: String,
        appliedPolicies: List<String> = emptyList(),
        failedPolicies: List<String> = emptyList()
    ): Result<Unit> = runCatching {
        val deviceId = getDeviceId() ?: error("Device ID não encontrado")
        val api = ApiClient.getInstance(context)
        val request = com.elion.mdm.data.remote.dto.StateReportRequest(
            health = health.name,
            reasonCode = reason,
            policyHash = policyHash,
            appliedPolicies = appliedPolicies,
            failedPolicies = failedPolicies
        )
        
        val response = api.reportStatus(deviceId, request)
        if (!response.isSuccessful) {
            error("Falha ao reportar status: HTTP ${response.code()}")
        }
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
