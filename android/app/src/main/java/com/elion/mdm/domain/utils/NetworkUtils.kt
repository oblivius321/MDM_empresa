package com.elion.mdm.domain.utils

import android.util.Log
import kotlinx.coroutines.delay

object NetworkUtils {

    /**
     * Retry com fallback exponencial para chamadas de rede.
     * Padrão (3 tentativas):
     *  - t1 = original
     *  - falhou -> wait 1s -> t2
     *  - falhou -> wait 2s -> t3
     *  - falhou -> wait 5s -> throw exceção
     */
    suspend fun <T> retryWithBackoff(
        times: Int = 3,
        initialDelayMs: Long = 1000,
        factor: Double = 2.0,
        maxDelayMs: Long = 5000,
        block: suspend () -> T
    ): T {
        var currentDelay = initialDelayMs
        repeat(times - 1) { attempt ->
            try {
                return block()
            } catch (e: Exception) {
                Log.w("NetworkUtils", "Falha na tentativa ${attempt + 1}. Retentando em ${currentDelay}ms. Erro: ${e.message}")
                delay(currentDelay)
                currentDelay = (currentDelay * factor).toLong().coerceAtMost(maxDelayMs)
            }
        }
        // Última tentativa sem catcher – se falhar, sobe para o chamador reportar localmente
        return block()
    }

    /**
     * Retorna o tipo de rede ativo no Device (Wi-Fi, Celular, etc.) para fins de Telemetria.
     */
    fun getNetworkType(context: android.content.Context): String {
        val cm = context.getSystemService(android.content.Context.CONNECTIVITY_SERVICE) as? android.net.ConnectivityManager ?: return "unknown"
        val activeNetwork = cm.activeNetwork ?: return "offline"
        val capabilities = cm.getNetworkCapabilities(activeNetwork) ?: return "offline"

        return when {
            capabilities.hasTransport(android.net.NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            capabilities.hasTransport(android.net.NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
            capabilities.hasTransport(android.net.NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
            else -> "other"
        }
    }
}
