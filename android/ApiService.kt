package com.elion.mdm.data.remote

import com.elion.mdm.data.remote.dto.*
import retrofit2.Response
import retrofit2.http.*

/**
 * ApiService — interface Retrofit mapeando os endpoints do Elion MDM backend.
 *
 * Autenticação: header "Authorization: Bearer <device_token>" injetado
 * automaticamente pelo AuthInterceptor em todas as requisições após enrollment.
 */
interface ApiService {

    // ─── Enrollment ───────────────────────────────────────────────────────────
    // Não requer token — usa bootstrap_secret para se autenticar pela 1ª vez.

    @POST("api/device/enroll")
    suspend fun enroll(
        @Body request: EnrollmentRequest
    ): Response<EnrollmentResponse>

    // ─── Check-in ─────────────────────────────────────────────────────────────

    @POST("api/device/checkin")
    suspend fun checkin(
        @Body request: CheckinRequest
    ): Response<CheckinResponse>

    // ─── Commands ─────────────────────────────────────────────────────────────

    @GET("api/device/commands")
    suspend fun getPendingCommands(): Response<List<DeviceCommand>>

    @POST("api/device/commands/{id}/complete")
    suspend fun completeCommand(
        @Path("id") commandId: Long,
        @Body request: CommandCompleteRequest
    ): Response<Unit>

    // ─── Policy ───────────────────────────────────────────────────────────────

    @GET("api/device/policy")
    suspend fun getPolicy(): Response<PolicyResponse>
}
