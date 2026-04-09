package com.elion.mdm.system

import android.content.Context
import android.util.Log
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class LogEntry(
    val timestamp: String,
    val type: String,
    val message: String
)

object LocalLogger {
    private const val MAX_LOGS = 100
    private const val FILE_NAME = "elion_agent_logs.json"
    
    private val scope = CoroutineScope(Dispatchers.IO)
    private val mutex = Mutex()
    private val logs = ArrayDeque<LogEntry>(MAX_LOGS + 10)
    private var isInitialized = false

    fun init(context: Context) {
        if (isInitialized) return
        scope.launch {
            mutex.withLock {
                val file = File(context.filesDir, FILE_NAME)
                if (file.exists()) {
                    try {
                        val content = file.readText()
                        val type = object : TypeToken<List<LogEntry>>() {}.type
                        val persistedLogs: List<LogEntry> = Gson().fromJson(content, type) ?: emptyList()
                        logs.addAll(persistedLogs)
                    } catch (e: Exception) {
                        Log.e("LocalLogger", "Falha ao ler logs persistidos: ${e.message}")
                    }
                }
                isInitialized = true
            }
        }
    }

    fun log(context: Context, type: String, message: String) {
        val safeMessage = maskSecrets(message)
        val entry = LogEntry(
            timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date()),
            type = type,
            message = safeMessage
        )

        Log.d("LocalLogger", "[$type] $safeMessage")

        scope.launch {
            mutex.withLock {
                if (logs.size >= MAX_LOGS) {
                    logs.removeFirst()
                }
                logs.addLast(entry)
                flushToDisk(context)
            }
        }
    }

    private fun flushToDisk(context: Context) {
        try {
            val file = File(context.filesDir, FILE_NAME)
            val json = Gson().toJson(logs)
            file.writeText(json)
        } catch (e: Exception) {
            Log.e("LocalLogger", "Falha escrevendo logs ao disco: ${e.message}")
        }
    }

    private fun maskSecrets(text: String): String {
        // Redact keywords to prevent leakage
        var safe = text
        val keywords = listOf("password", "token", "bootstrap_secret", "secret")
        keywords.forEach { kw ->
            // Simples regex to mask the value portion e.g. "token":"xxx" -> "token":"***"
            val regex = "(?i)(\"$kw\"\\s*:\\s*\")[^\"]+(\")".toRegex()
            safe = safe.replace(regex, "$1***$2")
        }
        return safe
    }
    
    fun getLogs(): List<LogEntry> = logs.toList()
}
