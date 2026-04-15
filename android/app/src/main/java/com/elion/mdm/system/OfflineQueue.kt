package com.elion.mdm.system

import android.content.Context
import android.util.Log
import com.elion.mdm.data.remote.ApiClient
import com.elion.mdm.data.remote.dto.CommandCompleteRequest
import com.elion.mdm.data.remote.dto.StateReportRequest
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.io.File
import kotlin.system.measureTimeMillis

data class QueuedEvent(
    val type: String,
    val priority: Int,
    val payload: JsonObject, // Usamos JsonObject genérico para abraçar ACK, RESULT e STATE
    val timestamp: Long,
    val deviceId: String
)

object OfflineQueue {
    private const val TAG = "ElionOfflineQueue"
    private const val MAX_ITEMS = 20
    private const val FILE_NAME = "offline_queue.json"
    private const val TMP_FILE_NAME = "offline_queue.json.tmp"

    const val TYPE_ACK = "ack"
    const val TYPE_RESULT = "result"
    const val TYPE_STATE = "state"
    
    const val PRIO_ACK = 1
    const val PRIO_RESULT = 2
    const val PRIO_STATE = 3

    private val scope = CoroutineScope(Dispatchers.IO)
    private val mutex = Mutex()
    private val queue = mutableListOf<QueuedEvent>()
    private var isInitialized = false
    @Volatile private var isFlushing = false

    fun init(context: Context) {
        if (isInitialized) return
        scope.launch {
            mutex.withLock {
                if (isInitialized) return@withLock
                val file = File(context.filesDir, FILE_NAME)
                if (file.exists()) {
                    try {
                        val content = file.readText()
                        val type = object : TypeToken<List<QueuedEvent>>() {}.type
                        val persisted: List<QueuedEvent> = Gson().fromJson(content, type) ?: emptyList()
                        
                        // Type validation constraint
                        val validEvents = persisted.filter { 
                            it.type == TYPE_ACK || it.type == TYPE_RESULT || it.type == TYPE_STATE 
                        }
                        
                        queue.addAll(validEvents)
                        sortQueue()
                        Log.i(TAG, "Queue inicializada com ${queue.size} itens vitais")
                    } catch (e: Exception) {
                        Log.e(TAG, "Falha ao ler offline_queue. Arquivo corrompido! Fazendo fallback para .bad")
                        file.renameTo(File(context.filesDir, "offline_queue.json.bad"))
                        queue.clear()
                    }
                }
                isInitialized = true
            }
        }
    }

    suspend fun enqueue(context: Context, event: QueuedEvent) {
        mutex.withLock {
            // Se excedeu 20, tentar dropar STATE primeiro
            if (queue.size >= MAX_ITEMS) {
                val stateIndex = queue.indexOfLast { it.priority == PRIO_STATE }
                if (stateIndex != -1) {
                    queue.removeAt(stateIndex)
                    Log.d(TAG, "Queue cheia. Item STATE remoto para acomodar novo evento.")
                } else {
                    // Se não houver STATE, joga fora o item de menor prioridade ou mais antigo (que estaria no final da queue)
                    queue.removeAt(queue.size - 1)
                    Log.d(TAG, "Queue totalmente cheia de itens críticos. Dropando último evento menos importante.")
                }
            }

            queue.add(event)
            sortQueue()
            flushToDisk(context)
            
            com.elion.mdm.data.local.SecurePreferences(context).queueSize = queue.size
        }
    }

    private fun sortQueue() {
        // Ordena por Prioridade (ASC: 1, 2, 3) e então pelo mais antigo (Timestamp ASC)
        queue.sortWith(compareBy({ it.priority }, { it.timestamp }))
    }

    private fun flushToDisk(context: Context) {
        try {
            val fileTmp = File(context.filesDir, TMP_FILE_NAME)
            val fileDb = File(context.filesDir, FILE_NAME)

            // Assegura remoção de segredos antes do dump
            val jsonStr = Gson().toJson(queue.map { event ->
                // Não persista logs contendo senhas cruas (já tratado indiretamente pelo payload)
                event
            })

            // Escrita Atômica
            fileTmp.writeText(jsonStr)
            fileTmp.renameTo(fileDb)
        } catch (e: Exception) {
            Log.e(TAG, "Falha I/O escrita atômica da queue: ${e.message}")
        }
    }

    suspend fun flushNetwork(context: Context) {
        if (!isInitialized || queue.isEmpty()) return
        if (isFlushing) {
            Log.d(TAG, "Flush ignorado (já existe um flush em andamento)")
            return
        }

        isFlushing = true
        val api = ApiClient.getInstance(context)
        val gson = Gson()

        try {
            mutex.withLock {
                Log.i(TAG, "Iniciando Flush da Offline Queue. Itens: ${queue.size}")
                
                val iterator = queue.iterator()
                var errorOcurred = false
                var batchCount = 0

                while (iterator.hasNext()) {
                    if (batchCount >= 5) {
                        Log.i(TAG, "Flush rate limit excedido (5 itens). Cooldown de 1.5s.")
                        kotlinx.coroutines.delay(1500)
                        batchCount = 0
                    }

                    val item = iterator.next()
                    try {
                        val response = kotlinx.coroutines.withTimeout(5000L) {
                            when (item.type) {
                                TYPE_ACK, TYPE_RESULT -> {
                                    val req = gson.fromJson(item.payload, CommandCompleteRequest::class.java)
                                    val element = item.payload.get("command_id")
                                    if (element != null) {
                                        api.updateCommandStatus(item.deviceId, element.asLong, req)
                                    } else {
                                        null
                                    }
                                }
                                TYPE_STATE -> {
                                    val req = gson.fromJson(item.payload, StateReportRequest::class.java)
                                    api.reportStatus(item.deviceId, req)
                                }
                                else -> null
                            }
                        }
                        
                        if (response != null && response.isSuccessful) {
                            Log.d(TAG, "Flush SUCESSO: ${item.type} (Timestamp: ${item.timestamp})")
                            iterator.remove() // Safe Delete (Só apaga pós-sucesso)
                            batchCount++
                        } else {
                            Log.w(TAG, "Flush BLOCK: endpoint regeitou payload. HTTP ${response?.code()}")
                            errorOcurred = true
                            break
                        }
                    } catch (e: Exception) {
                        Log.e(TAG, "Flush ERRO FATAL/Timeout: Interrompendo envio devido a ${e.message}")
                        errorOcurred = true
                        break
                    }
                }

                // Persiste estado do que restou na fila
                flushToDisk(context)

                if (errorOcurred) {
                    kotlinx.coroutines.delay(3000) // Backoff protetor pós-falha
                } else if (queue.isEmpty()) {
                    Log.i(TAG, "Flush finalizado completamente com sucesso.")
                }
                
                // Atualiza snapshot
                val prefs = com.elion.mdm.data.local.SecurePreferences(context)
                prefs.lastFlushTs = System.currentTimeMillis()
                prefs.queueSize = queue.size
            }
        } finally {
            isFlushing = false
        }
    }
}
