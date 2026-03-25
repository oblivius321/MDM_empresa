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
class EnrollDeviceUseCase(private val context: Context) {

    private val repository = DeviceRepository(context)
    private val dpm        = DevicePolicyHelper(context)

    suspend operator fun invoke(
        bootstrapSecret: String,
        backendUrl: String
    ): Result<EnrollmentResponse> {
        val result = repository.enroll(bootstrapSecret, backendUrl)

        result.onSuccess {
            // Inicia o serviço MDM imediatamente após enrollment
            MDMForegroundService.start(context)

            // Aplica restrições de segurança base (best-effort — não falha o enrollment)
            if (dpm.isDeviceOwner()) {
                dpm.setFactoryResetDisabled(true)
                    .onFailure { /* ignora — DO pode não estar ativo ainda */ }
                dpm.setSafeModeDisabled(true)
                    .onFailure { /* ignora */ }
            }
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
