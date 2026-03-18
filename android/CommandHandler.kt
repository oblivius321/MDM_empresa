package com.elion.mdm.domain

import android.content.Context
import android.content.Intent
import android.util.Log
import com.elion.mdm.data.remote.ApiClient
import com.elion.mdm.data.remote.dto.CommandCompleteRequest
import com.elion.mdm.data.remote.dto.CommandType
import com.elion.mdm.data.remote.dto.DeviceCommand
import com.elion.mdm.services.ApkInstallerService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * CommandHandler — roteador e executor de comandos remotos.
 *
 * Fluxo por comando:
 *   1. Recebe DeviceCommand do backend (via polling ou WebSocket)
 *   2. Roteia para o método correto com base em command.type
 *   3. Executa a operação via DevicePolicyHelper
 *   4. Notifica o backend: POST /device/commands/{id}/complete
 *
 * Erros são capturados individualmente — um comando com falha não
 * bloqueia a execução dos próximos na fila.
 */
class CommandHandler(private val context: Context) {

    companion object {
        private const val TAG = "ElionCommandHandler"
    }

    private val api = ApiClient.getInstance(context)
    private val dpm = DevicePolicyHelper(context)

    // ─── Ponto de entrada ─────────────────────────────────────────────────────

    suspend fun processCommands(commands: List<DeviceCommand>) {
        if (commands.isEmpty()) return
        Log.i(TAG, "Processando ${commands.size} comando(s)...")
        commands.forEach { executeCommand(it) }
    }

    // ─── Dispatcher ───────────────────────────────────────────────────────────

    private suspend fun executeCommand(command: DeviceCommand) = withContext(Dispatchers.IO) {
        Log.i(TAG, "Executando #${command.id}: ${command.type}")

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

        notifyBackend(command.id, result)
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

    private fun handleKioskEnable(command: DeviceCommand) {
        val pkg = command.payload["package"]
            ?: context.packageName   // default: o próprio agente MDM

        dpm.setKioskPackages(arrayOf(pkg)).getOrThrow()

        // Inicia Lock Task na Activity principal do pacote alvo
        val launchIntent = context.packageManager
            .getLaunchIntentForPackage(pkg)
            ?.apply { addFlags(Intent.FLAG_ACTIVITY_NEW_TASK) }

        launchIntent?.let { context.startActivity(it) }
        Log.i(TAG, "KIOSK_ENABLE para: $pkg")
    }

    private fun handleKioskDisable() {
        dpm.setKioskPackages(emptyArray()).getOrThrow()
        Log.i(TAG, "KIOSK_DISABLE executado")
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

        val intent = Intent(context, ApkInstallerService::class.java).apply {
            putExtra(ApkInstallerService.EXTRA_APK_URL, url)
        }
        context.startForegroundService(intent)
        Log.i(TAG, "INSTALL_APK enfileirado: $url")
    }

    private fun handleReboot() {
        dpm.reboot().getOrThrow()
        Log.i(TAG, "REBOOT solicitado")
    }

    private suspend fun handleSyncPolicy() {
        val response = api.getPolicy()
        if (response.isSuccessful) {
            response.body()?.let { policy ->
                dpm.applyPolicy(
                    cameraDisabled       = policy.cameraDisabled,
                    statusBarDisabled    = policy.statusBarDisabled,
                    minPasswordLength    = policy.minPasswordLength,
                    screenTimeoutSeconds = policy.screenTimeoutSeconds
                )
                if (policy.kioskModeEnabled && !policy.kioskPackage.isNullOrBlank()) {
                    dpm.setKioskPackages(arrayOf(policy.kioskPackage!!)).getOrThrow()
                }
                Log.i(TAG, "SYNC_POLICY aplicada")
            }
        } else {
            error("Falha ao buscar policy: ${response.code()}")
        }
    }

    // ─── Notificação ao backend ────────────────────────────────────────────────

    private suspend fun notifyBackend(commandId: Long, result: Result<*>) {
        val req = if (result.isSuccess) {
            CommandCompleteRequest(status = "success")
        } else {
            CommandCompleteRequest(
                status  = "failed",
                message = result.exceptionOrNull()?.message ?: "Erro desconhecido"
            )
        }

        runCatching {
            api.completeCommand(commandId, req)
        }.onFailure {
            Log.e(TAG, "Falha ao notificar backend para #$commandId: ${it.message}")
        }

        if (result.isFailure) {
            Log.e(TAG, "Comando #$commandId FALHOU: ${result.exceptionOrNull()?.message}")
        } else {
            Log.i(TAG, "Comando #$commandId concluído com SUCESSO")
        }
    }
}
