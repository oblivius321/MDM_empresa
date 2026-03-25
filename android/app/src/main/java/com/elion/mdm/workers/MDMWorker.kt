package com.elion.mdm.workers

import android.content.Context
import android.os.Build
import android.util.Log
import androidx.work.*
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.data.remote.ApiClient
import com.elion.mdm.data.remote.dto.CheckinRequest
import com.elion.mdm.domain.CommandHandler
import com.elion.mdm.domain.DevicePolicyHelper
import java.util.concurrent.TimeUnit

/**
 * MDMWorker — worker do WorkManager como camada de redundância ao ForegroundService.
 *
 * O WorkManager garante execução mesmo se:
 *   • O ForegroundService for morto pelo sistema em baixa memória
 *   • O dispositivo reiniciar (WorkManager persiste jobs no banco)
 *   • O app for forçado a fechar pelo usuário
 *
 * Este worker executa check-in + busca de comandos a cada N minutos,
 * sendo agendado periodicamente com PeriodicWorkRequest.
 *
 * O intervalo mínimo do WorkManager é 15 minutos (limitação do sistema).
 * Para intervalos menores (ex: 60s), o ForegroundService é obrigatório.
 */
class MDMWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    companion object {
        private const val TAG       = "ElionMDMWorker"
        const val WORK_NAME         = "elion_mdm_periodic_worker"
        private const val INTERVAL_MINUTES = 15L

        /**
         * Agenda o worker periódico. Seguro chamar múltiplas vezes — usa
         * ExistingPeriodicWorkPolicy.KEEP para não recriar se já existir.
         */
        fun schedule(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val request = PeriodicWorkRequestBuilder<MDMWorker>(
                INTERVAL_MINUTES, TimeUnit.MINUTES
            )
                .setConstraints(constraints)
                .setBackoffCriteria(
                    BackoffPolicy.EXPONENTIAL,
                    WorkRequest.MIN_BACKOFF_MILLIS,
                    TimeUnit.MILLISECONDS
                )
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request
            )

            Log.i(TAG, "MDMWorker agendado (intervalo: ${INTERVAL_MINUTES}min)")
        }

        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
            Log.i(TAG, "MDMWorker cancelado")
        }
    }

    // ─── Execução ─────────────────────────────────────────────────────────────

    override suspend fun doWork(): Result {
        val prefs = SecurePreferences(applicationContext)

        if (!prefs.hasValidToken()) {
            Log.w(TAG, "Dispositivo não enrollado — worker sem ação")
            return Result.success()
        }

        return runCatching {
            performCheckin(prefs)
            fetchCommands()
            Log.i(TAG, "MDMWorker concluído com sucesso")
        }.fold(
            onSuccess = { Result.success() },
            onFailure = { err ->
                Log.e(TAG, "MDMWorker falhou: ${err.message}")
                Result.retry()
            }
        )
    }

    // ─── Check-in ─────────────────────────────────────────────────────────────

    private suspend fun performCheckin(prefs: SecurePreferences) {
        val api      = ApiClient.getInstance(applicationContext)
        val dpm      = DevicePolicyHelper(applicationContext)
        val deviceId = prefs.deviceId ?: return

        val request = CheckinRequest(
            deviceId         = deviceId,
            batteryLevel     = getBatteryLevel(),
            deviceModel      = "${Build.MANUFACTURER} ${Build.MODEL}",
            androidVersion   = Build.VERSION.RELEASE,
            complianceStatus = if (dpm.isDeviceOwner()) "compliant" else "non_compliant"
        )

        val response = api.checkin(request)
        if (response.isSuccessful) {
            prefs.lastSyncTimestamp = System.currentTimeMillis()
            response.body()?.checkinInterval?.let {
                if (it > 0) prefs.checkinIntervalSeconds = it
            }
            Log.i(TAG, "Check-in OK via Worker")
        } else {
            error("Check-in HTTP ${response.code()}")
        }
    }

    // ─── Commands ─────────────────────────────────────────────────────────────

    private suspend fun fetchCommands() {
        val api      = ApiClient.getInstance(applicationContext)
        val response = api.getPendingCommands()

        if (response.isSuccessful) {
            val commands = response.body() ?: emptyList()
            if (commands.isNotEmpty()) {
                CommandHandler(applicationContext).processCommands(commands)
            }
        } else {
            error("Command fetch HTTP ${response.code()}")
        }
    }

    // ─── Utilitários ──────────────────────────────────────────────────────────

    private fun getBatteryLevel(): Int {
        val bm = applicationContext.getSystemService(Context.BATTERY_SERVICE)
                as android.os.BatteryManager
        return bm.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY)
    }
}
