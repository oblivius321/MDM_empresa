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

    // ─── Admin Authentication ─────────────────────────────────────────────────
    // Usado pelo kiosk para autenticar administradores localmente no dispositivo.

    @POST("api/auth/login")
    suspend fun adminLogin(
        @Body request: AdminLoginRequest
    ): Response<AdminLoginResponse>

    // ─── Enrollment ───────────────────────────────────────────────────────────
    // Endpoint: POST /api/enroll

    @POST("api/enroll")
    suspend fun enroll(
        @Body request: EnrollmentRequest
    ): Response<EnrollmentResponse>

    // ─── Check-in ─────────────────────────────────────────────────────────────
    // Endpoint: POST /api/devices/{id}/checkin

    @POST("api/devices/{device_id}/checkin")
    suspend fun checkin(
        @Path("device_id") deviceId: String,
        @Body request: CheckinRequest
    ): Response<CheckinResponse>

    // ─── Commands ─────────────────────────────────────────────────────────────
    // Endpoint: GET /api/devices/{id}/commands/pending

    @GET("api/devices/{device_id}/commands/pending")
    suspend fun getPendingCommands(
        @Path("device_id") deviceId: String
    ): Response<List<DeviceCommand>>

    // ─── Commands Ack ─────────────────────────────────────────────────────────
    // Endpoint: POST /api/devices/{id}/commands/{cmd_id}/ack

    @POST("api/devices/{device_id}/commands/{command_id}/ack")
    suspend fun acknowledgeCommand(
        @Path("device_id") deviceId: String,
        @Path("command_id") commandId: Long
    ): Response<Unit>

    @POST("api/devices/{device_id}/commands/{command_id}/status")
    suspend fun updateCommandStatus(
        @Path("device_id") deviceId: String,
        @Path("command_id") commandId: Long,
        @Body request: CommandCompleteRequest
    ): Response<Unit>

    // ─── Policy ───────────────────────────────────────────────────────────────
    // Nota: Backend atualizado para devices/{id}/policy se necessário

    @GET("api/devices/{device_id}/policy")
    suspend fun getPolicy(
        @Path("device_id") deviceId: String
    ): Response<PolicyResponse>

    // ─── Bootstrap (SSOT) ─────────────────────────────────────────────────────────
    // Recupera o estado completo para provisionamento ou recuperação.

    @GET("api/devices/{device_id}/bootstrap")
    suspend fun getBootstrapData(
        @Path("device_id") deviceId: String
    ): Response<BootstrapResponse>

    // ─── Status Report (Compliance) ───────────────────────────────────────────────
    // Envia relatório detalhado de saúde e conformidade (Enterprise 3B).

    @POST("api/devices/{device_id}/status")
    suspend fun reportStatus(
        @Path("device_id") deviceId: String,
        @Body request: StateReportRequest
    ): Response<Unit>

    // ─── File Download ────────────────────────────────────────────────────────
    
    @Streaming
    @GET
    suspend fun downloadFile(@Url url: String): Response<okhttp3.ResponseBody>

    // ─── Trust & Attestation (Phase 4) ────────────────────────────────────────
    
    @GET("api/devices/nonce")
    suspend fun getAttestationNonce(): Response<NonceResponse>

    @POST("api/devices/attest")
    suspend fun verifyAttestation(
        @Body request: AttestationRequest
    ): Response<Map<String, Any>>
}
