package com.elion.mdm.workers

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

class ApkInstallerWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    companion object {
        const val KEY_APK_URL = "apk_url"
        const val KEY_APK_SHA256 = "apk_sha256"
        private const val TAG = "ApkInstallerWorker"
    }

    override suspend fun doWork(): Result {
        val url = inputData.getString(KEY_APK_URL)
        if (url.isNullOrBlank()) {
            Log.e(TAG, "URL invalida ou nula")
            return Result.failure()
        }

        Log.i(TAG, "Iniciando download e instalacao do APK: $url")
        val installResult = com.elion.mdm.system.ApkSilentInstaller.downloadAndInstall(
            applicationContext,
            url,
            inputData.getString(KEY_APK_SHA256)
        )

        return if (installResult.isSuccess) {
            Result.success()
        } else {
            val error = installResult.exceptionOrNull()
            Log.e(TAG, "Falha na instalacao do APK: ${error?.message}")
            if (runAttemptCount < 2) Result.retry() else Result.failure()
        }
    }
}
