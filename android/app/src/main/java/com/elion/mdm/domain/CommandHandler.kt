package com.elion.mdm.domain

import android.content.Context
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.data.remote.ApiClient
import com.elion.mdm.data.remote.dto.CommandType
import com.elion.mdm.data.remote.dto.DeviceCommand
import com.elion.mdm.domain.utils.NetworkUtils
import com.elion.mdm.system.KioskManager
import com.elion.mdm.system.LocalLogger
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray

class CommandHandler(private val context: Context) {

    companion object {
        private const val TAG = "ElionCommandHandler"
        private const val STATUS_EXECUTED = "EXECUTED"
        private const val STATUS_FAILED = "FAILED"
    }

    private val prefs = SecurePreferences(context)
    private val api = ApiClient.getInstance(context)
    private val dpm = DevicePolicyHelper(context)
    private val kioskManager = KioskManager(context)
    private val prefsKeys = "elion_executed_commands"

    suspend fun processCommands(commands: List<DeviceCommand>) {
        if (commands.isEmpty()) return
        Log.i(TAG, "Processando ${commands.size} comando(s)...")
        commands.forEach { executeCommand(it) }
    }

    private fun isCommandExecuted(commandId: Long): Boolean {
        val sharedPrefs = context.getSharedPreferences(prefsKeys, Context.MODE_PRIVATE)
        return sharedPrefs.getBoolean(commandId.toString(), false)
    }

    private fun markCommandExecuted(commandId: Long) {
        val sharedPrefs = context.getSharedPreferences(prefsKeys, Context.MODE_PRIVATE)
        sharedPrefs.edit().putBoolean(commandId.toString(), true).apply()
    }

    private suspend fun executeCommand(command: DeviceCommand) = withContext(Dispatchers.IO) {
        if (isCommandExecuted(command.id)) {
            Log.w(TAG, "Comando #${command.id} ja foi executado. Reenviando resultado idempotente.")
            notifyBackend(command.id, STATUS_EXECUTED, "Ja executado anteriormente")
            return@withContext
        }

        val commandType = command.type.uppercase()
        Log.i(TAG, "Recebido #${command.id}: $commandType")

        val result = runCatching {
            when (commandType) {
                CommandType.LOCK -> handleLock()
                CommandType.WIPE -> handleWipe(command)
                CommandType.KIOSK_ENABLE,
                CommandType.ENABLE_KIOSK -> handleKioskEnable(command)
                CommandType.KIOSK_DISABLE,
                CommandType.DISABLE_KIOSK,
                CommandType.EXIT_KIOSK -> handleKioskDisable()
                CommandType.CAMERA_DISABLE -> handleCamera(disabled = true)
                CommandType.CAMERA_ENABLE -> handleCamera(disabled = false)
                CommandType.STATUS_BAR_DISABLE -> handleStatusBar(disabled = true)
                CommandType.STATUS_BAR_ENABLE -> handleStatusBar(disabled = false)
                CommandType.INSTALL_APK,
                CommandType.INSTALL_APP -> handleInstallApk(command)
                CommandType.REBOOT -> handleReboot()
                CommandType.SYNC_POLICY -> handleSyncPolicy()
                else -> error("Tipo desconhecido: $commandType")
            }
        }

        if (result.isSuccess) {
            markCommandExecuted(command.id)
            notifyBackend(command.id, STATUS_EXECUTED, null)
            Log.i(TAG, "Comando #${command.id} concluido com sucesso")
        } else {
            val errorMsg = result.exceptionOrNull()?.message ?: "Erro desconhecido"
            notifyBackend(command.id, STATUS_FAILED, errorMsg)
            Log.e(TAG, "Comando #${command.id} falhou: $errorMsg")
        }

        StateReporter(context).reportState()
    }

    private fun handleLock() {
        dpm.lockNow().getOrThrow()
        Log.i(TAG, "LOCK executado")
    }

    private fun handleWipe(command: DeviceCommand) {
        val includeExternal = payloadBoolean(command, "include_external_storage", "wipe_external_storage") == true
        dpm.wipeDevice(includeExternal).getOrThrow()
        Log.w(TAG, "WIPE executado (includeExternal=$includeExternal)")
    }

    private fun handleKioskEnable(command: DeviceCommand) {
        val allowedPackages = payloadStringList(command, "allowed_packages", "allowed_apps", "packages")
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

    private suspend fun handleInstallApk(command: DeviceCommand) {
        val url = payloadString(command, "url", "apk_url")
            ?: error("Payload 'url' obrigatorio para INSTALL_APK")
        val expectedHash = payloadString(command, "sha256", "apk_sha256", "checksum", "hash")

        com.elion.mdm.system.ApkSilentInstaller
            .downloadAndInstall(context, url, expectedHash)
            .getOrThrow()
        Log.i(TAG, "INSTALL_APK concluido: $url")
    }

    private fun handleReboot() {
        dpm.reboot().getOrThrow()
        Log.i(TAG, "REBOOT solicitado")
    }

    private suspend fun handleSyncPolicy() {
        val bootstrap = com.elion.mdm.data.repository.DeviceRepository(context)
            .bootstrapData()
            .getOrThrow()

        val dpmService = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as android.app.admin.DevicePolicyManager
        val admin = com.elion.mdm.AdminReceiver.getComponentName(context)
        val failedSteps = PolicyManager(context, dpmService, admin).applyFullPolicy(bootstrap)

        if (failedSteps.isNotEmpty()) {
            error("Falha ao aplicar policy: $failedSteps")
        }
        Log.i(TAG, "SYNC_POLICY aplicada via bootstrap (kiosk=${bootstrap.kioskEnabled})")
    }

    private suspend fun notifyBackend(commandId: Long, status: String, message: String?) {
        val req = com.elion.mdm.data.remote.dto.CommandCompleteRequest(
            status = status,
            errorMessage = message
        )
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

            val gson = com.google.gson.Gson()
            val payloadObj = gson.toJsonTree(req).asJsonObject
            payloadObj.addProperty("command_id", commandId)

            val qType = if (status == STATUS_EXECUTED || status == STATUS_FAILED) {
                com.elion.mdm.system.OfflineQueue.TYPE_RESULT
            } else {
                com.elion.mdm.system.OfflineQueue.TYPE_ACK
            }
            val qPrio = if (qType == com.elion.mdm.system.OfflineQueue.TYPE_RESULT) {
                com.elion.mdm.system.OfflineQueue.PRIO_RESULT
            } else {
                com.elion.mdm.system.OfflineQueue.PRIO_ACK
            }

            com.elion.mdm.system.OfflineQueue.enqueue(
                context,
                com.elion.mdm.system.QueuedEvent(
                    type = qType,
                    priority = qPrio,
                    payload = payloadObj,
                    timestamp = System.currentTimeMillis(),
                    deviceId = deviceId
                )
            )
        }
    }

    private fun payloadString(command: DeviceCommand, vararg keys: String): String? {
        return keys.firstNotNullOfOrNull { key ->
            command.payload[key]?.toString()?.trim()?.takeIf { it.isNotBlank() }
        }
    }

    private fun payloadBoolean(command: DeviceCommand, vararg keys: String): Boolean? {
        val value = keys.firstNotNullOfOrNull { key -> command.payload[key] } ?: return null
        return when (value) {
            is Boolean -> value
            is Number -> value.toInt() != 0
            is String -> value.equals("true", ignoreCase = true) || value == "1"
            else -> null
        }
    }

    private fun payloadStringList(command: DeviceCommand, vararg keys: String): List<String> {
        val value = keys.firstNotNullOfOrNull { key -> command.payload[key] } ?: return emptyList()
        return when (value) {
            is List<*> -> value.mapNotNull { it?.toString()?.trim() }.filter { it.isNotBlank() }
            is Array<*> -> value.mapNotNull { it?.toString()?.trim() }.filter { it.isNotBlank() }
            is String -> parseStringList(value)
            else -> emptyList()
        }
    }

    private fun parseStringList(value: String): List<String> {
        val text = value.trim()
        if (text.isBlank()) return emptyList()

        return if (text.startsWith("[")) {
            runCatching {
                val array = JSONArray(text)
                (0 until array.length())
                    .map { array.getString(it).trim() }
                    .filter { it.isNotBlank() }
            }.getOrElse { emptyList() }
        } else {
            text.split(",").map { it.trim() }.filter { it.isNotBlank() }
        }
    }
}
