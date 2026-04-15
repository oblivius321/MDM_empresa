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
            androidx.core.content.ContextCompat.startForegroundService(
                context, 
                Intent(context, MDMForegroundService::class.java)
            )
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, MDMForegroundService::class.java))
        }
    }

    private val exceptionHandler = kotlinx.coroutines.CoroutineExceptionHandler { _, exception ->
        android.util.Log.e(TAG, "Crash evitado na ForegroundService: ${exception.message}")
        com.elion.mdm.system.LocalLogger.log(this, "CRASH_PREVENTED", exception.message ?: "Unknown error")
    }
    private val serviceScope    = CoroutineScope(Dispatchers.IO + SupervisorJob() + exceptionHandler)
    private lateinit var prefs  : SecurePreferences
    private lateinit var cmdHandler: com.elion.mdm.domain.CommandHandler
    private lateinit var dpmHelper: DevicePolicyHelper
    private lateinit var policyManager: com.elion.mdm.domain.PolicyManager
    private lateinit var repository: com.elion.mdm.data.repository.DeviceRepository
    private lateinit var attestationService: com.elion.mdm.security.AttestationService

    private var checkinJob      : Job? = null
    private var commandPollJob  : Job? = null
    private var wsReconnectJob  : Job? = null
    private var kioskWatchdogJob: Job? = null
    private var webSocket       : WebSocket? = null
    private var isWsConnected   = false

    // ─── Lifecycle ────────────────────────────────────────────────────────────

    override fun onCreate() {
        super.onCreate()
        prefs = SecurePreferences(this)
        cmdHandler = com.elion.mdm.domain.CommandHandler(this)
        dpmHelper = DevicePolicyHelper(this)
        repository = com.elion.mdm.data.repository.DeviceRepository(this)
        attestationService = com.elion.mdm.security.AttestationService(this, com.elion.mdm.data.remote.ApiClient.getInstance(this))
        
        val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as android.app.admin.DevicePolicyManager
        val admin = com.elion.mdm.AdminReceiver.getComponentName(this)
        policyManager = com.elion.mdm.domain.PolicyManager(this, dpm, admin)

        com.elion.mdm.system.OfflineQueue.init(this)
        com.elion.mdm.system.LocalLogger.init(this)

        createNotificationChannel()
        startForeground(NOTIF_ID, buildNotification("Serviço em execução..."))
        Log.i(TAG, "MDMForegroundService criado — Modo Enterprise 3B")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.i(TAG, "onStartCommand")

        if (prefs.hasValidToken()) {
            startMDMEngine()
            connectWebSocket()
        } else {
            Log.w(TAG, "Dispositivo não enrollado — aguardando enrollment")
        }

        return START_STICKY
    }

    private fun startMDMEngine() {
        serviceScope.launch {
            while (isActive) {
                val stateInfo = com.elion.mdm.system.MDMStateMachine.getStateInfo(this@MDMForegroundService)
                
                if (stateInfo.isInCooldown()) {
                    Log.d(TAG, "Engine em COOLDOWN... aguardando.")
                    delay(30_000)
                    continue
                }

                when (stateInfo.state) {
                    com.elion.mdm.system.MDMState.INIT -> {
                        // Aguarda enrollment via UI (Phase 3A automatismo seria disparado aqui)
                        delay(10_000)
                    }
                    com.elion.mdm.system.MDMState.REGISTERING -> {
                        // Enrollment em curso
                        delay(2000)
                    }
                    com.elion.mdm.system.MDMState.PROVISIONING -> {
                        runBootstrap()
                    }
                    com.elion.mdm.system.MDMState.ENFORCING -> {
                        runEnforcement()
                    }
                    com.elion.mdm.system.MDMState.OPERATIONAL -> {
                        // Loop normal de manutenção
                        performCheckin()
                        
                        // ✅ NOVO (Fase 4): Atestação de Hardware Periódica
                        // Executa apenas se não houver atestação recente ou se solicitado pelo backend
                        attestationService.performAttestation().onFailure {
                             Log.w(TAG, "Atestação de hardware falhou (vulnerabilidade potencial): ${it.message}")
                        }

                        startKioskWatchdogLoop() // Reaproveita o watchdog
                        delay(prefs.checkinIntervalSeconds * 1000L)
                    }
                    com.elion.mdm.system.MDMState.ERROR -> {
                        Log.e(TAG, "Estado de ERRO detectado: ${stateInfo.lastError}")
                        // Se falhou muitas vezes, o transitionTo já cuidou do cooldown
                        delay(60_000)
                    }
                }
            }
        }
    }

    private suspend fun runBootstrap() {
        Log.i(TAG, "Iniciando PROVISIONING (Handshake SSOT)")
        repository.bootstrapData().onSuccess { bootstrap ->
            // Salva dados locais da política (será usado pelo ComplianceManager/PolicyManager)
            // Transição para aplicação
            com.elion.mdm.system.MDMStateMachine.transitionTo(
                this, 
                com.elion.mdm.system.MDMState.ENFORCING,
                metadata = mapOf("policy_hash" to bootstrap.policyHash)
            )
        }.onFailure {
            com.elion.mdm.system.MDMStateMachine.transitionTo(
                this, 
                com.elion.mdm.system.MDMState.ERROR, 
                error = "Bootstrap falhou: ${it.message}"
            )
        }
    }

    private suspend fun runEnforcement() {
        Log.i(TAG, "Iniciando ENFORCING (Ordem Determinística)")
        val bootstrapResult = repository.bootstrapData() // Recupera SSOT novamente para garantir atomicidade
        
        bootstrapResult.onSuccess { bootstrap ->
            val failedSteps = policyManager.applyFullPolicy(bootstrap)
            
            if (failedSteps.isEmpty()) {
                Log.i(TAG, "Conformidade Total Atingida!")
                com.elion.mdm.system.MDMStateMachine.transitionTo(this, com.elion.mdm.system.MDMState.OPERATIONAL)
                repository.reportStatus(com.elion.mdm.data.remote.dto.DeviceHealth.COMPLIANT, "INITIAL_ENFORCE", bootstrap.policyHash)
            } else {
                Log.e(TAG, "Falha parcial no enforcement: $failedSteps")
                com.elion.mdm.system.MDMStateMachine.transitionTo(this, com.elion.mdm.system.MDMState.ERROR, error = "Steps failed: $failedSteps")
                repository.reportStatus(
                    com.elion.mdm.data.remote.dto.DeviceHealth.DEGRADED, 
                    "PARTIAL_FAILURE: $failedSteps", 
                    bootstrap.policyHash,
                    failedPolicies = failedSteps
                )
            }
        }.onFailure {
             com.elion.mdm.system.MDMStateMachine.transitionTo(this, com.elion.mdm.system.MDMState.ERROR, error = it.message)
        }
    }

    private fun startKioskWatchdogLoop() {
        kioskWatchdogJob?.cancel()
        kioskWatchdogJob = serviceScope.launch {
            while (isActive) {
                if (prefs.isKioskEnabled && !dpmHelper.isInLockTaskMode()) {
                    Log.e(TAG, "🔥 CENTRAL WATCHDOG: Modo Kiosk Corrompido/Desligado detectado! Forçando reentrada Imediata.")
                    com.elion.mdm.launcher.KioskLauncherActivity.launch(this@MDMForegroundService)
                }
                delay(15_000) // Verificação constante a cada 15 segundos
            }
        }
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
            complianceStatus = if (dpmHelper.isDeviceOwner()) "compliant" else "non_compliant"
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
                if (System.currentTimeMillis() < circuitBreakerCooldownUntil) {
                     Log.w(TAG, "Circuit Breaker OPEN. Pulando HTTP polling c/ backend.")
                     delay(30_000)
                     continue
                }

                if (!isWsConnected) {
                    runCatching { fetchAndExecuteCommands() }
                        .onFailure { Log.e(TAG, "Command poll falhou: ${it.message}") }
                }
                delay(30_000) // poll a cada 30s APENAS como fallback ao WebSocket
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
        val deviceId = prefs.deviceId ?: return
        val baseUrl  = ApiClient.normalizeRootUrl(prefs.backendUrl)
            .replace("https://", "wss://")
            .replace("http://", "ws://")
        val wsUrl    = "${baseUrl.trimEnd('/')}/api/ws/device/$deviceId"

        val client   = OkHttpClient.Builder()
            .pingInterval(20, TimeUnit.SECONDS)
            .build()

        val request  = Request.Builder()
            .url(wsUrl)
            .addHeader("X-Device-Token", token)
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {

            override fun onOpen(ws: WebSocket, response: Response) {
                Log.i(TAG, "WebSocket CONECTADO")
                isWsConnected = true
                consecutiveFailures = 0 // CIRCUIT BREAKER RESET
                prefs.lastWsConnectedAt = System.currentTimeMillis()
                prefs.wsReconnectCount = 0
                wsReconnectJob?.cancel()

                serviceScope.launch {
                    kotlinx.coroutines.delay(500) // Delay tático antes do flush
                    com.elion.mdm.system.OfflineQueue.flushNetwork(this@MDMForegroundService)
                }
            }

            override fun onMessage(ws: WebSocket, text: String) {
                Log.d(TAG, "WebSocket mensagem: $text")
                serviceScope.launch {
                    runCatching {
                        // Tenta dar parse direto na mensagem como um DeviceCommand
                        val gson = com.google.gson.Gson()
                        val command = gson.fromJson(text, com.elion.mdm.data.remote.dto.DeviceCommand::class.java)
                        
                        if (command != null && command.id != 0L && command.type.isNotEmpty()) {
                            Log.i(TAG, "Comando WS parseado com sucesso: #${command.id} do tipo ${command.type}")
                            cmdHandler.processCommands(listOf(command))
                        } else {
                            // Se for apenas um 'ping' genérico, cai de volta para buscar os comandos
                            Log.d(TAG, "Mensagem WS não é um comando válido, disparando fetch de comandos pendentes...")
                            fetchAndExecuteCommands()
                        }
                    }.onFailure { 
                        Log.e(TAG, "Falha ao processar mensagem do WS (${it.message}), disparando fetch...")
                        fetchAndExecuteCommands()
                    }
                }
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                Log.w(TAG, "WebSocket FALHA: ${t.message} — reconectando em ${WS_RECONNECT_MS}ms")
                isWsConnected = false
                prefs.wsReconnectCount += 1
                prefs.lastErrorCode = t.message
                scheduleWsReconnect()
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                Log.w(TAG, "WebSocket FECHADO ($code: $reason) — reconectando...")
                isWsConnected = false
                scheduleWsReconnect()
            }
        })
    }

    private var consecutiveFailures = 0
    private var circuitBreakerCooldownUntil = 0L

    private fun scheduleWsReconnect() {
        val now = System.currentTimeMillis()
        if (now < circuitBreakerCooldownUntil) {
            Log.w(TAG, "Circuit Breaker OPEN. Pulando reconexão até ${formatTime(circuitBreakerCooldownUntil)}.")
            return
        }

        consecutiveFailures++
        val baseDelay = WS_RECONNECT_MS
        
        // Backoff exponencial e Circuit Breaker
        val delayMs = if (consecutiveFailures > 5) {
            Log.e(TAG, "💥 CIRCUIT BREAKER OPEN (Failed $consecutiveFailures times). Pausa forçada de 5 minutos.")
            circuitBreakerCooldownUntil = now + (5 * 60 * 1000) // 5 minutos freeze
            5 * 60 * 1000L
        } else {
            // Exponential backoff com max = 60s
            (baseDelay * Math.pow(2.0, consecutiveFailures.toDouble() - 1)).toLong().coerceAtMost(60_000L)
        }
        
        wsReconnectJob?.cancel()
        wsReconnectJob = serviceScope.launch {
            Log.w(TAG, "Agendando reconexão para daqui a ${delayMs / 1000}s (Tentativa: $consecutiveFailures)")
            delay(delayMs)
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
