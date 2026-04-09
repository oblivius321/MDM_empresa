package com.elion.mdm.security

import android.content.Context
import android.util.Log
import com.elion.mdm.data.remote.ApiService
import com.elion.mdm.data.remote.dto.AttestationRequest
import com.google.android.play.core.integrity.IntegrityManagerFactory
import com.google.android.play.core.integrity.IntegrityTokenRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AttestationService @Inject constructor(
    private val context: Context,
    private val api: ApiService
) {
    private val TAG = "ElionAttestation"

    /**
     * Executa o ciclo completo de atestação:
     * 1. GET Nonce
     * 2. Request Integrity Token (Google)
     * 3. POST Attestation Verify
     */
    suspend fun performAttestation(): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            Log.i(TAG, "Iniciando ciclo de atestação de hardware...")

            // 1. Obter Nonce do Backend
            val nonceResponse = api.getAttestationNonce()
            if (!nonceResponse.isSuccessful) {
                return@withContext Result.failure(Exception("Falha ao obter nonce: ${nonceResponse.code()}"))
            }

            val nonce = nonceResponse.body()?.nonce ?: return@withContext Result.failure(Exception("Nonce vazio"))

            // 2. Solicitar Token da Google Play Integrity API
            val integrityManager = IntegrityManagerFactory.create(context)
            
            val tokenRequest = IntegrityTokenRequest.builder()
                .setNonce(nonce)
                .build()

            // Converte a Task do Google em Coroutine
            val integrityToken = try {
                val task = integrityManager.requestIntegrityToken(tokenRequest)
                // Usamos um mecanismo de espera síncrona/blocking no IO thread para simplificar 
                // (Em prod real, usar suspendCoroutine ou await do play-services-tasks-ktx)
                com.google.android.gms.tasks.Tasks.await(task).token()
            } catch (e: Exception) {
                Log.e(TAG, "Erro ao chamar Play Integrity API: ${e.message}")
                return@withContext Result.failure(e)
            }

            // 3. Enviar para validação no Backend
            val verifyResponse = api.verifyAttestation(
                AttestationRequest(
                    integrity_token = integrityToken,
                    nonce = nonce
                )
            )

            if (verifyResponse.isSuccessful) {
                val result = verifyResponse.body()
                Log.i(TAG, "Atestação concluída! Trust Score: ${result?.get("trust_score")}")
                Result.success(Unit)
            } else {
                Log.e(TAG, "Backend rejeitou a atestação: ${verifyResponse.code()}")
                Result.failure(Exception("Atestação negada pelo servidor"))
            }

        } catch (e: Exception) {
            Log.e(TAG, "Falha crítica no fluxo de atestação", e)
            Result.failure(e)
        }
    }
}
