package com.example.androidmdm.network

import android.content.Context
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class MDMWebSocketClient(private val context: Context, private val deviceId: String) {
    private var webSocket: WebSocket? = null
    private var isConnected = false
    private val scope = CoroutineScope(Dispatchers.IO)
    private val client = OkHttpClient.Builder()
        .pingInterval(30, TimeUnit.SECONDS) // Keep-alive firewall
        .build()

    fun connect() {
        if (isConnected) return

        // Pega a ROOT BASE URL da API e troca http por ws
        val baseUrl = RetrofitClient.getBaseUrl()
        val wsUrl = if (baseUrl.startsWith("https")) {
            baseUrl.replace("https://", "wss://") + "api/ws/device/$deviceId"
        } else {
            baseUrl.replace("http://", "ws://") + "api/ws/device/$deviceId"
        }
        
        // Pega o token para conectar na malha segura
        val prefs = context.getSharedPreferences("ElionMDMPrefs", Context.MODE_PRIVATE)
        val deviceToken = prefs.getString("DEVICE_TOKEN", "") ?: ""

        val request = Request.Builder()
            .url(wsUrl)
            .addHeader("x-device-token", deviceToken)
            .build()
        
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i("MDMWebSocket", "🔌 Túnel Direto MDM Aberto com Sucesso!")
                isConnected = true
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                Log.d("MDMWebSocket", "📥 Comando RealTime Recebido: $text")
                try {
                    val json = JSONObject(text)
                    val commandStr = json.optString("command")
                    
                    // Emite BroadCast intent local pro MDMService engatilhar a bomba
                    val intent = android.content.Intent("com.example.androidmdm.COMMAND_RECEIVED")
                    intent.putExtra("command", commandStr)
                    
                    if (json.has("payload")) {
                        intent.putExtra("payload", json.optJSONObject("payload")?.toString())
                    }
                    
                    // Dispara a intent internamente (não exportada para fora do app)
                    intent.setPackage(context.packageName)
                    context.sendBroadcast(intent)
                    
                } catch (e: Exception) {
                    Log.e("MDMWebSocket", "Erro no Parse do JSON Socket: ${e.message}")
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
                isConnected = false
                Log.w("MDMWebSocket", "⚠️ Conexão Fechada Pelo Servidor.")
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("MDMWebSocket", "❌ Falha Catastrófica no Túnel Socket: ${t.message}")
                isConnected = false
                reconnect()
            }
        })
    }

    private fun reconnect() {
        scope.launch {
            Log.i("MDMWebSocket", "Tentando reerguer túnel em 10 segundos...")
            delay(10000)
            connect()
        }
    }

    fun disconnect() {
        webSocket?.close(1000, "Device Shutdown")
        isConnected = false
    }
}
