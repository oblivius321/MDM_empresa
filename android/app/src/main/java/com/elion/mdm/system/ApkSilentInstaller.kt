package com.elion.mdm.system

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageInstaller
import android.util.Log
import com.elion.mdm.data.remote.ApiClient
import com.elion.mdm.domain.utils.NetworkUtils
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.io.InputStream
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
            Log.i(TAG, "Iniciando processo de download e Silent Install: $apkUrl")

            val api = ApiClient.getInstance(context)
            
            // Tenta baixar com Backoff
            val byteStream = NetworkUtils.retryWithBackoff(3, 2000) {
                val response = api.downloadFile(apkUrl)
                if (!response.isSuccessful) {
                    throw Exception("Erro HTTP ao baixar APK: ${response.code()}")
                }
                response.body()?.byteStream() ?: throw Exception("Corpo do APK vazio")
            }

            Log.i(TAG, "APK retornado do pipeline de rede. Gravando Sessão no PackageInstaller...")
            installApkStream(context, byteStream)
        }
    }

    private suspend fun installApkStream(context: Context, inputStream: InputStream) {
        val packageInstaller = context.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
        
        var sessionId = -1
        try {
            sessionId = packageInstaller.createSession(params)
            val session = packageInstaller.openSession(sessionId)

            val out = session.openWrite("ElionAppPayload", 0, -1)
            
            Log.d(TAG, "Copiando binário massivo para o disco do sistema Android...")
            inputStream.use { input ->
                out.use { output ->
                    input.copyTo(output)
                    session.fsync(output)
                }
            }

            Log.d(TAG, "Cópia concluída. Comprometendo Sessão...")

            suspendCancellableCoroutine<Unit> { continuation ->
                val receiver = object : BroadcastReceiver() {
                    override fun onReceive(c: Context, intent: Intent) {
                        val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)
                        val message = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "Mensagem não provida"
                        
                        context.unregisterReceiver(this)

                        when (status) {
                            PackageInstaller.STATUS_SUCCESS -> {
                                Log.i(TAG, "Instalação Silenciosa Mestre concluída com Êxito!")
                                continuation.resume(Unit)
                            }
                            else -> {
                                Log.e(TAG, "Erro de Instalação Silenciosa OS(Status: $status): $message")
                                continuation.resumeWith(Result.failure(Exception("SilentInstall OS Failure: $message")))
                            }
                        }
                    }
                }

                // API Nível 33+ requer FLAGS específicos para dynamic receivers
                val filter = IntentFilter(ACTION_INSTALL_COMPLETE)
                try {
                    context.registerReceiver(receiver, filter, Context.RECEIVER_EXPORTED)
                } catch (e: NoSuchMethodError) {
                    context.registerReceiver(receiver, filter) // Fallback API legada
                }

                val intent = Intent(ACTION_INSTALL_COMPLETE).apply {
                    setPackage(context.packageName)
                }
                
                val flags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
                val pendingIntent = PendingIntent.getBroadcast(context, sessionId, intent, flags)

                session.commit(pendingIntent.intentSender)
                
                // Em caso do job ser cancelado abruptamente no Kotlin
                continuation.invokeOnCancellation {
                    try {
                        context.unregisterReceiver(receiver)
                    } catch (e: Exception) {}
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Exceção fatal durante engine de instalação: ${e.message}")
            if (sessionId != -1) {
                try { packageInstaller.abandonSession(sessionId) } catch (ignore: Exception) {}
            }
            throw e
        }
    }
}
