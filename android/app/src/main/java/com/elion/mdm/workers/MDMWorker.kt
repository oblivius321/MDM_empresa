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
            fetchCommands(prefs)
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
        val ctx      = applicationContext

        // Bateria e carregamento
        val batteryStatus: android.content.Intent? = android.content.IntentFilter(
            android.content.Intent.ACTION_BATTERY_CHANGED
        ).let { ifilter -> ctx.registerReceiver(null, ifilter) }

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
        } catch (e: Exception) { null }

        // Apps instalados
        val installedApps: List<String>? = try {
            ctx.packageManager.getInstalledPackages(0).map { it.packageName }.sorted()
        } catch (e: Exception) { null }

        // GPS
        var latitude: Double? = null
        var longitude: Double? = null
        try {
            if (ctx.checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION)
                    == android.content.pm.PackageManager.PERMISSION_GRANTED ||
                ctx.checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION)
                    == android.content.pm.PackageManager.PERMISSION_GRANTED) {
                val lm = ctx.getSystemService(Context.LOCATION_SERVICE) as android.location.LocationManager
                val loc = lm.getLastKnownLocation(android.location.LocationManager.GPS_PROVIDER)
                    ?: lm.getLastKnownLocation(android.location.LocationManager.NETWORK_PROVIDER)
                latitude = loc?.latitude
                longitude = loc?.longitude
            }
        } catch (_: Exception) {}

        val request = CheckinRequest(
            batteryLevel     = batteryLevel,
            isCharging       = isCharging,
            deviceModel      = "${Build.MANUFACTURER} ${Build.MODEL}",
            androidVersion   = Build.VERSION.RELEASE,
            complianceStatus = if (dpm.isDeviceOwner()) "compliant" else "non_compliant",
            freeDiskSpaceMb  = freeDiskMb,
            installedApps    = installedApps,
            latitude         = latitude,
            longitude        = longitude
        )

        val response = api.checkin(deviceId, request)
        if (response.isSuccessful) {
            prefs.lastSyncTimestamp = System.currentTimeMillis()
            response.body()?.checkinInterval?.let {
                if (it > 0) prefs.checkinIntervalSeconds = it
            }
            Log.i(TAG, "Check-in OK via Worker — battery=${batteryLevel}% apps=${installedApps?.size ?: 0}")
        } else {
            error("Check-in HTTP ${response.code()}")
        }
    }

    // ─── Commands ─────────────────────────────────────────────────────────────

    private suspend fun fetchCommands(prefs: SecurePreferences) {
        val deviceId = prefs.deviceId ?: return
        val api      = ApiClient.getInstance(applicationContext)
        val response = api.getPendingCommands(deviceId)

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
