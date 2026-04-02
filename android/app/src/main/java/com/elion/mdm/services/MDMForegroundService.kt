package com.elion.mdm.services

import android.app.*
import android.os.BatteryManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.elion.mdm.R
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.data.remote.ApiClient
import com.elion.mdm.data.remote.dto.CheckinRequest
import com.elion.mdm.domain.CommandHandler
import com.elion.mdm.domain.DevicePolicyHelper
import com.elion.mdm.presentation.MainActivity
import kotlinx.coroutines.*
import okhttp3.*
import java.util.concurrent.TimeUnit

/**
 * MDMForegroundService — núcleo do agente MDM.
 *
 * Responsabilidades:
 *   1. Manter o processo vivo mesmo com o app em background
 *   2. Executar check-ins periódicos (telemetria → backend)
 *   3. Buscar e executar comandos pendentes (polling)
 *   4. Manter conexão WebSocket para comandos em tempo real
 *   5. Reconectar automaticamente ao WebSocket se cair
 *
 * O serviço usa um Foreground Service (obrigatório no Android 8+) com
 * uma notificação persistente para não ser morto pelo sistema.
 */
class MDMForegroundService : Service() {

    companion object {
        private const val TAG              = "ElionMDMService"
        private const val NOTIF_ID         = 1001
        private const val CHANNEL_ID       = "elion_mdm_service"
        private const val CHANNEL_NAME     = "Elion MDM Agent"
        private const val WS_RECONNECT_MS  = 10_000L  // 10 segundos entre tentativas de reconexão

        fun start(context: Context) {
            context.startForegroundService(Intent(context, MDMForegroundService::class.java))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, MDMForegroundService::class.java))
        }
    }

    private val serviceScope    = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private lateinit var prefs  : SecurePreferences
    private lateinit var cmdHandler: CommandHandler
    private lateinit var dpm    : DevicePolicyHelper

    private var checkinJob      : Job? = null
    private var commandPollJob  : Job? = null
    private var wsReconnectJob  : Job? = null
    private var webSocket       : WebSocket? = null

    // ─── Lifecycle ────────────────────────────────────────────────────────────

    override fun onCreate() {
        super.onCreate()
        prefs      = SecurePreferences(this)
        cmdHandler = CommandHandler(this)
        dpm        = DevicePolicyHelper(this)

        createNotificationChannel()
        startForeground(NOTIF_ID, buildNotification("Agente MDM ativo"))
        Log.i(TAG, "MDMForegroundService criado")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.i(TAG, "onStartCommand")

        if (prefs.hasValidToken()) {
            startCheckinLoop()
            startCommandPollLoop()
            connectWebSocket()
        } else {
            Log.w(TAG, "Dispositivo não enrollado — aguardando enrollment")
        }

        return START_STICKY  // reinicia automaticamente se o sistema matar o processo
    }

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
        webSocket?.close(1000, "Service destruído")
        Log.i(TAG, "MDMForegroundService destruído")
    }

    override fun onBind(intent: Intent?): IBinder? = null

    // ─── Check-in Loop ────────────────────────────────────────────────────────

    private fun startCheckinLoop() {
        checkinJob?.cancel()
        checkinJob = serviceScope.launch {
            while (isActive) {
                runCatching { performCheckin() }
                    .onFailure { Log.e(TAG, "Check-in falhou: ${it.message}") }

                val interval = prefs.checkinIntervalSeconds.toLong()
                Log.d(TAG, "Próximo check-in em ${interval}s")
                delay(interval * 1000)
            }
        }
    }

    private suspend fun performCheckin() {
        val api      = ApiClient.getInstance(this)
        val deviceId = prefs.deviceId ?: return

        val request = CheckinRequest(
            batteryLevel     = getBatteryLevel(),
            deviceModel      = "${Build.MANUFACTURER} ${Build.MODEL}",
            androidVersion   = Build.VERSION.RELEASE,
            complianceStatus = if (dpm.isDeviceOwner()) "compliant" else "non_compliant"
        )

        val response = api.checkin(deviceId, request)
        if (response.isSuccessful) {
            prefs.lastSyncTimestamp = System.currentTimeMillis()
            response.body()?.checkinInterval?.let {
                if (it > 0) prefs.checkinIntervalSeconds = it
            }
            Log.i(TAG, "Check-in OK — battery=${request.batteryLevel}%")
            updateNotification("Último sync: ${formatTime(prefs.lastSyncTimestamp)}")
        } else {
            Log.w(TAG, "Check-in HTTP ${response.code()}")
        }
    }

    // ─── Command Poll Loop ────────────────────────────────────────────────────

    private fun startCommandPollLoop() {
        commandPollJob?.cancel()
        commandPollJob = serviceScope.launch {
            while (isActive) {
                runCatching { fetchAndExecuteCommands() }
                    .onFailure { Log.e(TAG, "Command poll falhou: ${it.message}") }
                delay(30_000) // poll a cada 30s como fallback ao WebSocket
            }
        }
    }

    private suspend fun fetchAndExecuteCommands() {
        val deviceId = prefs.deviceId ?: return
        val api      = ApiClient.getInstance(this)
        val response = api.getPendingCommands(deviceId)

        if (response.isSuccessful) {
            val commands = response.body() ?: emptyList()
            if (commands.isNotEmpty()) {
                Log.i(TAG, "${commands.size} comando(s) pendente(s)")
                cmdHandler.processCommands(commands)
            }
        } else {
            Log.w(TAG, "Command poll HTTP ${response.code()}")
        }
    }

    // ─── WebSocket ────────────────────────────────────────────────────────────

    private fun connectWebSocket() {
        val token    = prefs.deviceToken ?: return
        val baseUrl  = prefs.backendUrl.replace("https://", "wss://").replace("http://", "ws://")
        val wsUrl    = "${baseUrl.trimEnd('/')}/ws/device?token=$token"

        val client   = OkHttpClient.Builder()
            .pingInterval(20, TimeUnit.SECONDS)
            .build()

        val request  = Request.Builder().url(wsUrl).build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {

            override fun onOpen(ws: WebSocket, response: Response) {
                Log.i(TAG, "WebSocket CONECTADO")
                wsReconnectJob?.cancel()
            }

            override fun onMessage(ws: WebSocket, text: String) {
                Log.d(TAG, "WebSocket mensagem: $text")
                // Trigger imediato de busca de comandos ao receber qualquer mensagem
                serviceScope.launch {
                    runCatching { fetchAndExecuteCommands() }
                        .onFailure { Log.e(TAG, "WS trigger falhou: ${it.message}") }
                }
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                Log.w(TAG, "WebSocket FALHA: ${t.message} — reconectando em ${WS_RECONNECT_MS}ms")
                scheduleWsReconnect()
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                Log.w(TAG, "WebSocket FECHADO ($code: $reason) — reconectando...")
                scheduleWsReconnect()
            }
        })
    }

    private fun scheduleWsReconnect() {
        wsReconnectJob?.cancel()
        wsReconnectJob = serviceScope.launch {
            delay(WS_RECONNECT_MS)
            connectWebSocket()
        }
    }

    // ─── Notificação ──────────────────────────────────────────────────────────

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            CHANNEL_NAME,
            NotificationManager.IMPORTANCE_LOW
        ).apply { description = "Elion MDM Agent — gerenciamento de dispositivo" }

        getSystemService(NotificationManager::class.java)
            .createNotificationChannel(channel)
    }

    private fun buildNotification(text: String): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Elion MDM")
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_mdm_agent)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun updateNotification(text: String) {
        val nm = getSystemService(NotificationManager::class.java)
        nm.notify(NOTIF_ID, buildNotification(text))
    }

    // ─── Helpers ──────────────────────────────────────────────────────────────

    private fun getBatteryLevel(): Int {
        val bm = getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        return bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
    }

    private fun formatTime(ms: Long): String {
        if (ms == 0L) return "nunca"
        val sdf = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault())
        return sdf.format(java.util.Date(ms))
    }
}
