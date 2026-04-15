package com.elion.mdm.security

import android.content.Context
import android.util.Log
import com.elion.mdm.data.remote.ApiService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class AttestationService(
    private val context: Context,
    private val api: ApiService
) {
    private val tag = "ElionAttestation"

    suspend fun performAttestation(): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val nonceResponse = api.getAttestationNonce()
            if (!nonceResponse.isSuccessful) {
                return@withContext Result.failure(Exception("Falha ao obter nonce: ${nonceResponse.code()}"))
            }

            val nonce = nonceResponse.body()?.nonce
            if (nonce.isNullOrBlank()) {
                return@withContext Result.failure(Exception("Nonce vazio"))
            }

            Log.w(tag, "Play Integrity nao esta empacotado neste build; atestacao ignorada.")
            Result.failure(UnsupportedOperationException("Play Integrity dependency not configured"))
        } catch (e: Exception) {
            Log.e(tag, "Falha no fluxo de atestacao", e)
            Result.failure(e)
        }
    }
}
