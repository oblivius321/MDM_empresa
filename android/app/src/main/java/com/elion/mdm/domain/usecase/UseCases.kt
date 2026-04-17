package com.elion.mdm.domain.usecase

import android.content.Context
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.data.remote.dto.EnrollmentResponse
import com.elion.mdm.data.repository.DeviceRepository
import com.elion.mdm.domain.DevicePolicyHelper
import com.elion.mdm.services.MDMForegroundService
import org.json.JSONArray

/**
 * EnrollDeviceUseCase — orquestra o processo completo de enrollment.
 *
 * Responsabilidades:
 *   1. Delega chamada de API ao DeviceRepository
 *   2. Em caso de sucesso, inicia o MDMForegroundService
 *   3. Aplica restrições iniciais de segurança via DevicePolicyHelper
 */
class EnrollDeviceUseCase(private val context: Context) {

    private val repository = DeviceRepository(context)
    private val prefs      = SecurePreferences(context)

    suspend fun enroll(
        bootstrapToken: String,
        backendUrl: String,
        profileId: String? = null
    ): Result<EnrollmentResponse> {
        // 1. Início do processo -> ENROLLING
        prefs.mdmState = com.elion.mdm.domain.MdmState.ENROLLING

        // Transição legada (compatibilidade temporária com o Reporter/StateMachine antigo se necessário)
        com.elion.mdm.system.MDMStateMachine.transitionTo(
            context, 
            com.elion.mdm.system.MDMState.REGISTERING,
            metadata = mapOf(
                "bootstrap_token" to bootstrapToken,
                "api_url" to backendUrl,
                "backend_url" to backendUrl,
                "profile_id" to (profileId ?: "")
            )
        )

        val result = repository.enroll(bootstrapToken, backendUrl, profileId)

        result.onSuccess {
            // 2. Sucesso -> ENROLLED
            prefs.mdmState = com.elion.mdm.domain.MdmState.ENROLLED

            com.elion.mdm.system.MDMStateMachine.transitionTo(
                context,
                com.elion.mdm.system.MDMState.PROVISIONING
            )
            
            // Inicia o serviço MDM que orquestrará o resto do ciclo de vida
            MDMForegroundService.start(context)
        }.onFailure {
            // 3. Falha -> Volta para UNCONFIGURED
            prefs.mdmState = com.elion.mdm.domain.MdmState.UNCONFIGURED

            com.elion.mdm.system.MDMStateMachine.transitionTo(
                context,
                com.elion.mdm.system.MDMState.ERROR,
                error = "Enrollment falhou: ${it.message}"
            )
        }

        return result
    }
}

// ─── GetDeviceStatusUseCase ───────────────────────────────────────────────────

/**
 * GetDeviceStatusUseCase — agrega o estado atual do dispositivo para a UI.
 */
class GetDeviceStatusUseCase(private val context: Context) {

    private val repository = DeviceRepository(context)
    private val dpm        = DevicePolicyHelper(context)
    private val prefs      = SecurePreferences(context)

    operator fun invoke(): DeviceStatus {
        val allowedPackages = readAllowedPackages()

        return DeviceStatus(
            isEnrolled       = repository.isEnrolled(),
            deviceId         = repository.getDeviceId(),
            lastSyncMs       = repository.getLastSyncTimestamp(),
            isDeviceOwner    = dpm.isDeviceOwner(),
            isCameraDisabled = dpm.isCameraDisabled(),
            isKioskEnabled   = prefs.isKioskEnabled,
            isLockTaskActive = dpm.isInLockTaskMode(),
            allowedPackages  = allowedPackages,
            kioskPackages    = dpm.getKioskPackages().toList()
        )
    }

    private fun readAllowedPackages(): List<String> {
        return try {
            val array = JSONArray(prefs.allowedAppsJson)
            (0 until array.length()).map { array.getString(it) }
        } catch (_: Exception) {
            emptyList()
        }
    }
}

// ─── Model de status ──────────────────────────────────────────────────────────

data class DeviceStatus(
    val isEnrolled      : Boolean,
    val deviceId        : String?,
    val lastSyncMs      : Long,
    val isDeviceOwner   : Boolean,
    val isCameraDisabled: Boolean,
    val isKioskEnabled  : Boolean,
    val isLockTaskActive: Boolean,
    val allowedPackages : List<String>,
    val kioskPackages   : List<String>
)
