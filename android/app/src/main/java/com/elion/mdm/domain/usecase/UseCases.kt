package com.elion.mdm.domain.usecase

import android.content.Context
import com.elion.mdm.data.remote.dto.EnrollmentResponse
import com.elion.mdm.data.repository.DeviceRepository
import com.elion.mdm.domain.DevicePolicyHelper
import com.elion.mdm.services.MDMForegroundService

/**
 * EnrollDeviceUseCase — orquestra o processo completo de enrollment.
 *
 * Responsabilidades:
 *   1. Delega chamada de API ao DeviceRepository
 *   2. Em caso de sucesso, inicia o MDMForegroundService
 *   3. Aplica restrições iniciais de segurança via DevicePolicyHelper
 */
    suspend fun enroll(
        bootstrapSecret: String,
        backendUrl: String,
        profileId: String? = null
    ): Result<EnrollmentResponse> {
        // Transição inicial para a Máquina de Estados (Crash-Safe)
        com.elion.mdm.system.MDMStateMachine.transitionTo(
            context, 
            com.elion.mdm.system.MDMState.REGISTERING,
            metadata = mapOf("backend_url" to backendUrl, "profile_id" to (profileId ?: ""))
        )

        val result = repository.enroll(bootstrapSecret, backendUrl) 

        result.onSuccess {
            // Transição para Provisionamento (Busca SSOT)
            com.elion.mdm.system.MDMStateMachine.transitionTo(
                context,
                com.elion.mdm.system.MDMState.PROVISIONING
            )
            
            // Inicia o serviço MDM que orquestrará o resto do ciclo de vida
            MDMForegroundService.start(context)
        }.onFailure {
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

    operator fun invoke(): DeviceStatus = DeviceStatus(
        isEnrolled      = repository.isEnrolled(),
        deviceId        = repository.getDeviceId(),
        lastSyncMs      = repository.getLastSyncTimestamp(),
        isDeviceOwner   = dpm.isDeviceOwner(),
        isCameraDisabled = dpm.isCameraDisabled(),
        kioskPackages   = dpm.getKioskPackages().toList()
    )
}

// ─── Model de status ──────────────────────────────────────────────────────────

data class DeviceStatus(
    val isEnrolled      : Boolean,
    val deviceId        : String?,
    val lastSyncMs      : Long,
    val isDeviceOwner   : Boolean,
    val isCameraDisabled: Boolean,
    val kioskPackages   : List<String>
)
