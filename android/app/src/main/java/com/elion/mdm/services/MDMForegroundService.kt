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
import com.elion.mdm.data.remote.dto.DeviceCommand
import com.elion.mdm.domain.CommandHandler
import com.elion.mdm.domain.DevicePolicyHelper
import com.elion.mdm.presentation.MainActivity
import com.elion.mdm.system.DevMode
import com.google.gson.Gson
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.google.gson.reflect.TypeToken
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
    private var engineJob       : Job? = null
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
        
        // Android 14+ exige o tipo do serviço no startForeground
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(
                NOTIF_ID, 
                buildNotification("Proteção MDM Ativa"), 
                android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE
            )
        } else {
            startForeground(NOTIF_ID, buildNotification("Proteção MDM Ativa"))
        }

        Log.i(TAG, "MDMForegroundService iniciado - DeviceID: ${prefs.deviceId}, URL: ${prefs.backendUrl}")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.i(TAG, "onStartCommand")

        if (prefs.hasValidToken()) {
            startMDMEngine()
            startCommandPollLoop()
            connectWebSocket()
        } else {
            Log.w(TAG, "Dispositivo não enrollado — aguardando enrollment")
        }

        return START_STICKY
    }

    private fun startMDMEngine() {
        if (engineJob?.isActive == true) return
        engineJob = serviceScope.launch {
            while (isActive) {
                val state = prefs.mdmState
                
                Log.d(TAG, "MDM Engine Tick - State: $state")

                when (state) {
                    com.elion.mdm.domain.MdmState.UNCONFIGURED -> {
                        // Aguarda enrollment
                        delay(10_000)
                    }
                    com.elion.mdm.domain.MdmState.ENROLLING -> {
                        // Enrollment em curso
                        delay(2000)
                    }
                    com.elion.mdm.domain.MdmState.ENROLLED,
                    com.elion.mdm.domain.MdmState.KIOSK_ACTIVE -> {
                        // Loop normal de manutenção
                        performCheckin()
                        if (state == com.elion.mdm.domain.MdmState.ENROLLED) {
                            runEnforcement()
                        }
                        
                        // Atestação de Hardware
                        attestationService.performAttestation().onFailure {
                             Log.w(TAG, "Atestação de hardware falhou: ${it.message}")
                        }

                        if (state == com.elion.mdm.domain.MdmState.KIOSK_ACTIVE) {
                            startKioskWatchdogLoop()
                        }
                        
                        delay(prefs.checkinIntervalSeconds * 1000L)
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
        if (DevMode.isDevMode()) {
            return
        }
        if (kioskWatchdogJob?.isActive == true) return
        
        kioskWatchdogJob = serviceScope.launch {
            while (isActive) {
                val state = prefs.mdmState
                if (state == com.elion.mdm.domain.MdmState.KIOSK_ACTIVE && !dpmHelper.isInLockTaskMode()) {
                    Log.e(TAG, "🔥 WATCHDOG: Kiosk violado! Forçando reentrada.")
                    com.elion.mdm.launcher.KioskLauncherActivity.launch(this@MDMForegroundService)
                }
                delay(15_000)
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
        val baseUrl = com.elion.mdm.data.remote.ApiClient.normalizeRootUrl(prefs.backendUrl)
        Log.i(TAG, "🚀 [CHECKIN] Iniciando envio para: $baseUrl")
        
        val deviceId = prefs.deviceId
        if (deviceId.isNullOrBlank()) {
            Log.e(TAG, "❌ [CHECKIN] Cancelado: Device ID nulo ou vazio")
            return
        }

        try {
        // ─── Coleta de Telemetria Rica ──────────────────────────────────────
        
        // Bateria e carregamento
        val batteryStatus: android.content.Intent? = android.content.IntentFilter(
            android.content.Intent.ACTION_BATTERY_CHANGED
        ).let { ifilter -> registerReceiver(null, ifilter) }

        val batteryLevel = batteryStatus?.let { intent ->
            val level = intent.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL, -1)
            val scale = intent.getIntExtra(android.os.BatteryManager.EXTRA_SCALE, -1)
            if (scale > 0) (level * 100 / scale.toFloat()).toInt() else getBatteryLevel()
        } ?: getBatteryLevel()

        val isCharging = batteryStatus?.let { intent ->
            val status = intent.getIntExtra(android.os.BatteryManager.EXTRA_STATUS, -1)
            status == android.os.BatteryManager.BATTERY_STATUS_CHARGING ||
                status == android.os.BatteryManager.BATTERY_STATUS_FULL
        } ?: false

        // Armazenamento livre
        val freeDiskMb: Int? = try {
            val stat = android.os.StatFs(android.os.Environment.getDataDirectory().path)
            (stat.availableBytes / (1024 * 1024)).toInt()
        } catch (e: Exception) {
            Log.w(TAG, "Falha ao obter espaço em disco: ${e.message}")
            null
        }

        // Apps instalados (package names)
        val installedApps: List<String>? = try {
            val flags = android.content.pm.PackageManager.GET_META_DATA
            val packages = packageManager.getInstalledPackages(flags)
            Log.i(TAG, "Check-in: Encontrados ${packages.size} apps instalados")
            packages.map { it.packageName }.sorted()
        } catch (e: Exception) {
            Log.w(TAG, "Falha ao listar apps: ${e.message}")
            null
        }

        // GPS (última localização conhecida — requer permissão)
        var latitude: Double? = null
        var longitude: Double? = null
        try {
            if (checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION)
                    == android.content.pm.PackageManager.PERMISSION_GRANTED ||
                checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION)
                    == android.content.pm.PackageManager.PERMISSION_GRANTED) {
                val locationManager = getSystemService(Context.LOCATION_SERVICE) as android.location.LocationManager
                val location = locationManager.getLastKnownLocation(android.location.LocationManager.GPS_PROVIDER)
                    ?: locationManager.getLastKnownLocation(android.location.LocationManager.NETWORK_PROVIDER)
                if (location != null) {
                    latitude = location.latitude
                    longitude = location.longitude
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "Falha ao obter GPS: ${e.message}")
        }

        // App em foreground (fallback seguro)
        var foregroundApp: String? = null
        try {
            val usm = getSystemService(Context.USAGE_STATS_SERVICE) as? android.app.usage.UsageStatsManager
            if (usm != null) {
                val end = System.currentTimeMillis()
                val begin = end - 60_000 // último minuto
                val stats = usm.queryUsageStats(android.app.usage.UsageStatsManager.INTERVAL_DAILY, begin, end)
                foregroundApp = stats?.maxByOrNull { it.lastTimeUsed }?.packageName
            }
        } catch (e: Exception) {
            Log.w(TAG, "Falha ao obter foreground app: ${e.message}")
        }

        // ─── Construção e envio do request ──────────────────────────────────

        val request = CheckinRequest(
            batteryLevel     = batteryLevel,
            isCharging       = isCharging,
            deviceModel      = "${Build.MANUFACTURER} ${Build.MODEL}",
            androidVersion   = Build.VERSION.RELEASE,
            imei             = dpmHelper.getImei() ?: "Aguardando Device Owner",
            serial           = dpmHelper.getSerialNumber() ?: Build.SERIAL,
            complianceStatus = if (dpmHelper.isDeviceOwner()) "compliant" else "non_compliant",
            freeDiskSpaceMb  = freeDiskMb,
            installedApps    = installedApps,
            latitude         = latitude,
            longitude        = longitude,
            foregroundApp    = foregroundApp
        )
        
        val api = ApiClient.getInstance(this)
        Log.d(TAG, "📦 [JSON] Enviando para /checkin: ${Gson().toJson(request)}")
        val response = api.checkin(deviceId, request)
        if (response.isSuccessful) {
            prefs.lastSyncTimestamp = System.currentTimeMillis()
            response.body()?.checkinInterval?.let {
                if (it > 0) prefs.checkinIntervalSeconds = it
            }
            Log.i(TAG, "Check-in OK — battery=${request.batteryLevel}% charging=${isCharging} disk=${freeDiskMb}MB apps=${installedApps?.size ?: 0} gps=${latitude != null}")
            updateNotification("Último sync: ${formatTime(prefs.lastSyncTimestamp)}")
        } else {
            Log.w(TAG, "Check-in HTTP ${response.code()}")
        }
        } catch (e: Exception) {
            Log.e(TAG, "Erro crítico no performCheckin: ${e.message}")
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
                runCatching { com.elion.mdm.system.OfflineQueue.flushNetwork(this@MDMForegroundService) }
                    .onFailure { Log.e(TAG, "OfflineQueue flush falhou: ${it.message}") }
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
        if (isWsConnected && webSocket != null) return
        webSocket?.cancel()
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
            .addHeader("X-MDM-MODE", DevMode.modeHeader())
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
                        if (replyToServerPingIfNeeded(ws, text)) {
                            return@runCatching
                        }

                        val command = parseWsCommand(text)
                        
                        if (command != null && command.id != 0L && command.type.isNotBlank()) {
                            Log.i(TAG, "Comando WS parseado com sucesso: #${command.id} do tipo ${command.type}")
                            cmdHandler.processCommands(listOf(command))
                        } else if (isWsControlMessage(text)) {
                            Log.d(TAG, "Mensagem WS de controle recebida")
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

    private fun replyToServerPingIfNeeded(ws: WebSocket, text: String): Boolean {
        val type = parseJsonObject(text)?.stringOrNull("type") ?: return false
        if (type.equals("server_ping", ignoreCase = true)) {
            ws.send("""{"type":"ping"}""")
            return true
        }
        return false
    }

    private fun isWsControlMessage(text: String): Boolean {
        val type = parseJsonObject(text)?.stringOrNull("type") ?: return false
        return type in setOf("CONNECTED", "connected", "pong", "error", "compliance_status", "server_ping")
    }

    private fun parseWsCommand(text: String): DeviceCommand? {
        val obj = parseJsonObject(text) ?: return null
        val envelopeType = obj.stringOrNull("type")

        if (envelopeType.equals("command", ignoreCase = true)) {
            val id = obj.longOrNull("command_id") ?: obj.longOrNull("id") ?: return null
            val action = obj.stringOrNull("action") ?: obj.stringOrNull("command_type") ?: return null
            return DeviceCommand(
                id = id,
                type = action,
                payload = jsonPayloadToMap(obj.get("payload"))
            )
        }

        val action = obj.stringOrNull("command_type") ?: obj.stringOrNull("action")
            ?: obj.stringOrNull("type")?.takeUnless { it.equals("command", ignoreCase = true) }
        val id = obj.longOrNull("id") ?: obj.longOrNull("command_id")

        if (id == null || action.isNullOrBlank() || isWsControlMessage(text)) {
            return null
        }

        return DeviceCommand(
            id = id,
            type = action,
            payload = jsonPayloadToMap(obj.get("payload"))
        )
    }

    private fun parseJsonObject(text: String): JsonObject? {
        return runCatching {
            val element = JsonParser.parseString(text)
            if (element.isJsonObject) element.asJsonObject else null
        }.getOrNull()
    }

    private fun JsonObject.stringOrNull(key: String): String? {
        val element = get(key) ?: return null
        if (element.isJsonNull) return null
        return runCatching { element.asString.trim().takeIf { it.isNotBlank() } }.getOrNull()
    }

    private fun JsonObject.longOrNull(key: String): Long? {
        val element = get(key) ?: return null
        if (element.isJsonNull) return null
        return runCatching { element.asLong }.getOrNull()
    }

    private fun jsonPayloadToMap(element: JsonElement?): Map<String, Any?> {
        if (element == null || element.isJsonNull || !element.isJsonObject) return emptyMap()
        val type = object : TypeToken<Map<String, Any?>>() {}.type
        return Gson().fromJson(element, type)
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
