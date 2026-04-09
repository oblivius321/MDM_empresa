package com.elion.mdm.domain

import android.content.Context
import android.content.Intent
import android.util.Log
import kotlinx.coroutines.withContext
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.data.remote.ApiClient
import com.elion.mdm.data.remote.dto.CommandType
import com.elion.mdm.data.remote.dto.DeviceCommand
import com.elion.mdm.system.KioskManager
import com.elion.mdm.system.LocalLogger
import com.elion.mdm.domain.utils.NetworkUtils
import kotlinx.coroutines.Dispatchers

/**
 * CommandHandler — roteador e executor de comandos remotos.
 *
 * Fluxo por comando:
 *   1. Recebe DeviceCommand do backend (via polling ou WebSocket)
 *   2. Roteia para o método correto com base em command.type
 *   3. Executa a operação via DevicePolicyHelper / KioskManager
 *   4. Notifica o backend: POST /device/commands/{id}/complete
 */
class CommandHandler(private val context: Context) {

    companion object {
        private const val TAG = "ElionCommandHandler"
    }

    private val prefs = SecurePreferences(context)
    private val api = ApiClient.getInstance(context)
    private val dpm = DevicePolicyHelper(context)
    private val kioskManager = KioskManager(context)

    // ─── Ponto de entrada ─────────────────────────────────────────────────────

    suspend fun processCommands(commands: List<DeviceCommand>) {
        if (commands.isEmpty()) return
        Log.i(TAG, "Processando ${commands.size} comando(s)...")
        commands.forEach { executeCommand(it) }
    }

    // ─── Dispatcher ───────────────────────────────────────────────────────────

    private val prefsKeys = "elion_executed_commands" // Chave raiz para simplificar

    private fun isCommandExecuted(commandId: Long): Boolean {
        val sharedPrefs = context.getSharedPreferences(prefsKeys, Context.MODE_PRIVATE)
        return sharedPrefs.getBoolean(commandId.toString(), false)
    }

    private fun markCommandExecuted(commandId: Long) {
        val sharedPrefs = context.getSharedPreferences(prefsKeys, Context.MODE_PRIVATE)
        sharedPrefs.edit().putBoolean(commandId.toString(), true).apply()
        // Opcional: Para evitar crescimento infinito, o ideal seria ter um TTL ou manter apenas os ultimos 100 ids
    }

    private suspend fun executeCommand(command: DeviceCommand) = withContext(Dispatchers.IO) {
        if (isCommandExecuted(command.id)) {
            Log.w(TAG, "Comando #${command.id} já foi executado. Ignorando para garantir idempotência.")
            notifyBackend(command.id, "acknowledged", "Já executado anteriormente (idempotência)")
            return@withContext
        }

        Log.i(TAG, "Recebido #${command.id}: ${command.type}. Enviando ACK...")
        // 1. ACK Imediato
        notifyBackend(command.id, "acknowledged", null)
        
        // 2. Marcar como executado
        markCommandExecuted(command.id)

        // 3. Execução Protegida
        val result = runCatching {
            when (command.type) {
                CommandType.LOCK               -> handleLock()
                CommandType.WIPE               -> handleWipe(command)
                CommandType.KIOSK_ENABLE       -> handleKioskEnable(command)
                CommandType.KIOSK_DISABLE      -> handleKioskDisable()
                CommandType.CAMERA_DISABLE     -> handleCamera(disabled = true)
                CommandType.CAMERA_ENABLE      -> handleCamera(disabled = false)
                CommandType.STATUS_BAR_DISABLE -> handleStatusBar(disabled = true)
                CommandType.STATUS_BAR_ENABLE  -> handleStatusBar(disabled = false)
                CommandType.INSTALL_APK        -> handleInstallApk(command)
                CommandType.REBOOT             -> handleReboot()
                CommandType.SYNC_POLICY        -> handleSyncPolicy()
                else -> error("Tipo desconhecido: ${command.type}")
            }
        }

        // 4. RESULT (Sucesso ou Falha)
        if (result.isSuccess) {
            notifyBackend(command.id, "success", null)
            Log.i(TAG, "Comando #${command.id} concluído com SUCESSO")
        } else {
            val errorMsg = result.exceptionOrNull()?.message ?: "Erro desconhecido"
            notifyBackend(command.id, "failed", errorMsg)
            Log.e(TAG, "Comando #${command.id} FALHOU: $errorMsg")
        }

        // 5. State Report (Automatic after state change)
        StateReporter(context).reportState()
    }

    // ─── Handlers ─────────────────────────────────────────────────────────────

    private fun handleLock() {
        dpm.lockNow().getOrThrow()
        Log.i(TAG, "LOCK executado")
    }

    private fun handleWipe(command: DeviceCommand) {
        val includeExternal = command.payload["include_external_storage"] == "true"
        dpm.wipeDevice(includeExternal).getOrThrow()
        Log.w(TAG, "WIPE executado (includeExternal=$includeExternal)")
    }

    /**
     * Ativa o modo kiosk usando o KioskManager (orquestrador).
     * Payload opcional: "allowed_packages" (JSON array de pacotes).
     */
    private fun handleKioskEnable(command: DeviceCommand) {
        val allowedPackages = command.payload["allowed_packages"]
            ?.let { json ->
                try {
                    val array = org.json.JSONArray(json)
                    (0 until array.length()).map { array.getString(it) }
                } catch (e: Exception) {
                    emptyList()
                }
            } ?: emptyList()

        kioskManager.enableKiosk(allowedPackages)
        Log.i(TAG, "KIOSK_ENABLE via KioskManager (${allowedPackages.size} apps)")
    }

    private fun handleKioskDisable() {
        kioskManager.disableKiosk()
        Log.i(TAG, "KIOSK_DISABLE via KioskManager")
    }

    private fun handleCamera(disabled: Boolean) {
        dpm.setCameraDisabled(disabled).getOrThrow()
        Log.i(TAG, "CAMERA disabled=$disabled")
    }

    private fun handleStatusBar(disabled: Boolean) {
        dpm.setStatusBarDisabled(disabled).getOrThrow()
        Log.i(TAG, "STATUS_BAR disabled=$disabled")
    }

    private fun handleInstallApk(command: DeviceCommand) {
        val url = command.payload["url"]
            ?: error("Payload 'url' obrigatório para INSTALL_APK")

        val data = androidx.work.Data.Builder()
            .putString(com.elion.mdm.workers.ApkInstallerWorker.KEY_APK_URL, url)
            .build()
            
        val workRequest = androidx.work.OneTimeWorkRequestBuilder<com.elion.mdm.workers.ApkInstallerWorker>()
            .setInputData(data)
            .build()
            
        androidx.work.WorkManager.getInstance(context).enqueue(workRequest)
        Log.i(TAG, "INSTALL_APK enfileirado no WorkManager: $url")
    }

    private fun handleReboot() {
        dpm.reboot().getOrThrow()
        Log.i(TAG, "REBOOT solicitado")
    }

    private suspend fun handleSyncPolicy() {
        val deviceId = prefs.deviceId ?: return
        val response = api.getPolicy(deviceId)
        if (response.isSuccessful) {
            response.body()?.let { policy ->
                dpm.applyPolicy(
                    cameraDisabled       = policy.cameraDisabled,
                    statusBarDisabled    = policy.statusBarDisabled,
                    minPasswordLength    = policy.minPasswordLength,
                    screenTimeoutSeconds = policy.screenTimeoutSeconds
                )
                if (policy.kioskModeEnabled) {
                    val allowedPkgs = policy.kioskPackage?.let { listOf(it) } ?: emptyList()
                    kioskManager.enableKiosk(allowedPkgs)
                } else {
                    kioskManager.disableKiosk()
                }
                Log.i(TAG, "SYNC_POLICY aplicada (kiosk=${policy.kioskModeEnabled})")
            }
        } else {
            error("Falha ao buscar policy: ${response.code()}")
        }
    }

    // ─── Notificação ao backend ────────────────────────────────────────────────

    private suspend fun notifyBackend(commandId: Long, status: String, message: String?) {
        val req = com.elion.mdm.data.remote.dto.CommandCompleteRequest(status = status, message = message)
        val deviceId = prefs.deviceId ?: return

        runCatching {
            NetworkUtils.retryWithBackoff(times = 3) {
                val response = api.updateCommandStatus(deviceId, commandId, req)
                if (!response.isSuccessful) {
                    throw Exception("HTTP ${response.code()}")
                }
            }
        }.onFailure {
            Log.e(TAG, "Falha ao notificar backend ($status) para #$commandId: ${it.message}")
            LocalLogger.log(context, "${status.uppercase()}_FAILED", "Comando #$commandId: ${it.message}")
            
            // Fallback para Store & Forward Offline Queue
            val gson = com.google.gson.Gson()
            val payloadObj = gson.toJsonTree(req).asJsonObject
            payloadObj.addProperty("command_id", commandId) // Injeta command_id para o parser futuro
            
            val qType = if (status == "success" || status == "failed") com.elion.mdm.system.OfflineQueue.TYPE_RESULT else com.elion.mdm.system.OfflineQueue.TYPE_ACK
            val qPrio = if (qType == com.elion.mdm.system.OfflineQueue.TYPE_RESULT) com.elion.mdm.system.OfflineQueue.PRIO_RESULT else com.elion.mdm.system.OfflineQueue.PRIO_ACK
            
            com.elion.mdm.system.OfflineQueue.enqueue(context, com.elion.mdm.system.QueuedEvent(
                type = qType,
                priority = qPrio,
                payload = payloadObj,
                timestamp = System.currentTimeMillis(),
                deviceId = deviceId
            ))
        }
    }
}
