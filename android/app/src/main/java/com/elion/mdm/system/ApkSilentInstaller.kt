package com.elion.mdm.system

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageInstaller
import android.util.Base64
import android.util.Log
import com.elion.mdm.data.remote.ApiClient
import com.elion.mdm.domain.utils.NetworkUtils
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.io.ByteArrayInputStream
import java.io.InputStream
import java.security.MessageDigest
import kotlin.coroutines.resume

object ApkSilentInstaller {

    private const val TAG = "ElionSilentInstaller"
    private const val ACTION_INSTALL_COMPLETE = "com.elion.mdm.INSTALL_COMPLETE"

    suspend fun downloadAndInstall(
        context: Context,
        apkUrl: String,
        expectedHash: String? = null
    ): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            Log.i(TAG, "Iniciando download e silent install: $apkUrl")

            val api = ApiClient.getInstance(context)
            val byteStream = NetworkUtils.retryWithBackoff(3, 2000) {
                val response = api.downloadFile(apkUrl)
                if (!response.isSuccessful) {
                    throw Exception("Erro HTTP ao baixar APK: ${response.code()}")
                }
                response.body()?.byteStream() ?: throw Exception("Corpo do APK vazio")
            }

            val apkBytes = byteStream.use { it.readBytes() }
            verifyExpectedHash(apkBytes, expectedHash)

            Log.i(TAG, "APK baixado. Gravando sessao no PackageInstaller...")
            installApkStream(context, ByteArrayInputStream(apkBytes))
        }
    }

    private fun verifyExpectedHash(apkBytes: ByteArray, expectedHash: String?) {
        val expected = expectedHash?.trim()?.takeIf { it.isNotBlank() } ?: return
        val digest = MessageDigest.getInstance("SHA-256").digest(apkBytes)
        val hex = digest.joinToString("") { "%02x".format(it) }
        val base64Url = Base64.encodeToString(
            digest,
            Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP
        )

        if (!expected.equals(hex, ignoreCase = true) && expected != base64Url) {
            throw IllegalStateException("Hash SHA-256 do APK nao confere")
        }
    }

    private suspend fun installApkStream(context: Context, inputStream: InputStream) {
        val packageInstaller = context.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)

        var sessionId = -1
        try {
            sessionId = packageInstaller.createSession(params)
            val session = packageInstaller.openSession(sessionId)

            session.openWrite("ElionAppPayload", 0, -1).use { output ->
                inputStream.use { input ->
                    input.copyTo(output)
                    session.fsync(output)
                }
            }

            suspendCancellableCoroutine<Unit> { continuation ->
                val receiver = object : BroadcastReceiver() {
                    override fun onReceive(c: Context, intent: Intent) {
                        val status = intent.getIntExtra(
                            PackageInstaller.EXTRA_STATUS,
                            PackageInstaller.STATUS_FAILURE
                        )
                        val message = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE)
                            ?: "Mensagem nao informada"

                        try {
                            context.unregisterReceiver(this)
                        } catch (_: Exception) {
                        }

                        when (status) {
                            PackageInstaller.STATUS_SUCCESS -> {
                                Log.i(TAG, "Instalacao silenciosa concluida")
                                continuation.resume(Unit)
                            }
                            else -> {
                                Log.e(TAG, "Falha PackageInstaller(status=$status): $message")
                                continuation.resumeWith(Result.failure(Exception("SilentInstall OS Failure: $message")))
                            }
                        }
                    }
                }

                val filter = IntentFilter(ACTION_INSTALL_COMPLETE)
                try {
                    context.registerReceiver(receiver, filter, Context.RECEIVER_EXPORTED)
                } catch (_: NoSuchMethodError) {
                    context.registerReceiver(receiver, filter)
                }

                val intent = Intent(ACTION_INSTALL_COMPLETE).apply {
                    setPackage(context.packageName)
                }

                val flags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
                val pendingIntent = PendingIntent.getBroadcast(context, sessionId, intent, flags)

                session.commit(pendingIntent.intentSender)

                continuation.invokeOnCancellation {
                    try {
                        context.unregisterReceiver(receiver)
                    } catch (_: Exception) {
                    }
                    try {
                        packageInstaller.abandonSession(sessionId)
                    } catch (_: Exception) {
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Excecao fatal durante instalacao: ${e.message}")
            if (sessionId != -1) {
                try {
                    packageInstaller.abandonSession(sessionId)
                } catch (_: Exception) {
                }
            }
            throw e
        }
    }
}
