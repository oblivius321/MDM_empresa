package com.example.androidmdm.network

import com.example.androidmdm.DeviceInventory
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

// Define the payload for check-in based on DeviceInventory class
data class CheckInPayload(
    val battery_level: Float,
    val is_charging: Boolean,
    val free_disk_space_mb: Long,
    val installed_apps: List<String>,
    // Advanced DPC Telemetry
    val latitude: Double?,
    val longitude: Double?,
    val foreground_app: String?,
    val daily_usage_stats: Map<String, Long>?
)

data class PendingCommand(
    val id: String,
    val command: String,
    val payload: com.google.gson.JsonObject?
)

data class CommandStatusPayload(
    val status: String,
    val result: String
)

interface ElionAPI {

    @POST("devices/{device_id}/checkin")
    suspend fun sendCheckIn(
        @Path("device_id") deviceId: String,
        @Body payload: CheckInPayload
    ): Response<Unit>

    @GET("devices/{device_id}/commands/pending")
    suspend fun getPendingCommands(
        @Path("device_id") deviceId: String
    ): Response<List<PendingCommand>>

    @POST("devices/{device_id}/commands/{command_id}/status")
    suspend fun updateCommandStatus(
        @Path("device_id") deviceId: String,
        @Path("command_id") commandId: String,
        @Body payload: CommandStatusPayload
    ): Response<Unit>
}
