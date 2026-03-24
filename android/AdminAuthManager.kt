package com.elion.mdm.security

import android.content.Context
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.data.remote.ApiClient
import com.elion.mdm.data.remote.dto.AdminLoginRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.security.MessageDigest

/**
 * AdminAuthManager — gerenciador de autenticação de administrador no kiosk.
 *
 * Fluxo de autenticação:
 *   1. Verificar se está em lockout (brute-force)
 *   2. Tentar autenticar via backend (FastAPI POST /auth/login)
 *   3. Fallback: verificar contra hash local (SHA-256)
 *   4. Gerenciar sessão com timeout de 5 minutos
 *
 * Proteção contra brute-force:
 *   - Máximo 5 tentativas
 *   - Lockout exponencial: 30s → 60s → 120s → 240s → 480s
 */
class AdminAuthManager(context: Context) {

    companion object {
        private const val TAG = "ElionAdminAuth"
        private const val MAX_ATTEMPTS = 5
        private const val BASE_LOCKOUT_MS = 30_000L  // 30 segundos
        private const val SESSION_DURATION_MS = 5 * 60 * 1000L  // 5 minutos
    }

    private val prefs = SecurePreferences(context)
    private val appContext = context.applicationContext

    // ─── Estado ───────────────────────────────────────────────────────────────

    fun isLockedOut(): Boolean {
        val until = prefs.lockoutUntilMs
        if (until <= 0L) return false
        if (System.currentTimeMillis() >= until) {
            // Lockout expirado
            prefs.resetLoginAttempts()
            return false
        }
        return true
    }

    fun getRemainingLockoutSeconds(): Long {
        val until = prefs.lockoutUntilMs
        if (until <= 0L) return 0
        val remaining = until - System.currentTimeMillis()
        return if (remaining > 0) remaining / 1000 else 0
    }

    fun getRemainingAttempts(): Int {
        return (MAX_ATTEMPTS - prefs.loginAttempts).coerceAtLeast(0)
    }

    fun hasValidSession(): Boolean = prefs.isSessionValid()

    // ─── Autenticação ─────────────────────────────────────────────────────────

    /**
     * Tenta autenticar o administrador.
     * Retorna true se autenticado com sucesso.
     */
    suspend fun authenticate(email: String, password: String): AuthResult {
        // 1. Verificar lockout
        if (isLockedOut()) {
            val remaining = getRemainingLockoutSeconds()
            Log.w(TAG, "Conta bloqueada por mais ${remaining}s")
            return AuthResult.LockedOut(remaining)
        }

        // 2. Tentar via backend
        val backendResult = tryBackendAuth(email, password)
        if (backendResult) {
            onAuthSuccess(email, password)
            return AuthResult.Success
        }

        // 3. Fallback: hash local
        val localResult = tryLocalAuth(email, password)
        if (localResult) {
            onAuthSuccess(email, password)
            return AuthResult.Success
        }

        // 4. Falha — incrementar tentativas
        return onAuthFailure()
    }

    // ─── Backend Auth ─────────────────────────────────────────────────────────

    private suspend fun tryBackendAuth(email: String, password: String): Boolean =
        withContext(Dispatchers.IO) {
            try {
                val api = ApiClient.getInstance(appContext)
                val response = api.adminLogin(AdminLoginRequest(email, password))

                if (response.isSuccessful) {
                    val body = response.body()
                    val isAdmin = body?.user?.isAdmin == true
                    if (isAdmin) {
                        Log.i(TAG, "Backend auth OK: $email (admin=true)")
                        return@withContext true
                    } else {
                        Log.w(TAG, "Backend auth OK mas usuário não é admin: $email")
                        return@withContext false
                    }
                } else {
                    Log.w(TAG, "Backend auth FALHOU: HTTP ${response.code()}")
                    return@withContext false
                }
            } catch (e: Exception) {
                Log.w(TAG, "Backend indisponível, tentando fallback local: ${e.message}")
                return@withContext false
            }
        }

    // ─── Local Auth (Fallback) ────────────────────────────────────────────────

    private fun tryLocalAuth(email: String, password: String): Boolean {
        val storedHash = prefs.adminPasswordHash ?: return false
        val storedEmail = prefs.adminEmail ?: return false

        if (email != storedEmail) return false

        val inputHash = hashPassword(password)
        val match = inputHash == storedHash
        Log.i(TAG, "Local auth: ${if (match) "OK" else "FALHOU"}")
        return match
    }

    /**
     * Salva credenciais de admin localmente (hash SHA-256).
     * Chamado após login bem-sucedido via backend para permitir fallback offline.
     */
    fun cacheCredentials(email: String, password: String) {
        prefs.adminEmail = email
        prefs.adminPasswordHash = hashPassword(password)
        Log.i(TAG, "Credenciais do admin cacheadas localmente")
    }

    // ─── Evento de Sucesso ────────────────────────────────────────────────────

    private fun onAuthSuccess(email: String, password: String) {
        prefs.resetLoginAttempts()
        prefs.sessionToken = generateSessionToken()
        prefs.sessionExpiryMs = System.currentTimeMillis() + SESSION_DURATION_MS

        // Cache para fallback offline
        cacheCredentials(email, password)

        Log.i(TAG, "Login bem-sucedido: $email (sessão válida por 5min)")
    }

    // ─── Evento de Falha ──────────────────────────────────────────────────────

    private fun onAuthFailure(): AuthResult {
        val attempts = prefs.loginAttempts + 1
        prefs.loginAttempts = attempts

        if (attempts >= MAX_ATTEMPTS) {
            // Lockout exponencial: 30s * 2^(falhas extras)
            val multiplier = (attempts - MAX_ATTEMPTS).coerceAtMost(4)
            val lockoutMs = BASE_LOCKOUT_MS * (1L shl multiplier)
            prefs.lockoutUntilMs = System.currentTimeMillis() + lockoutMs

            Log.w(TAG, "LOCKOUT ativado: ${lockoutMs / 1000}s (tentativa $attempts)")
            return AuthResult.LockedOut(lockoutMs / 1000)
        }

        val remaining = MAX_ATTEMPTS - attempts
        Log.w(TAG, "Auth falhou: $remaining tentativas restantes")
        return AuthResult.Failed(remaining)
    }

    // ─── Sessão ───────────────────────────────────────────────────────────────

    fun invalidateSession() {
        prefs.clearSession()
        Log.i(TAG, "Sessão invalidada")
    }

    // ─── Helpers ──────────────────────────────────────────────────────────────

    private fun hashPassword(password: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
        // Salt fixo derivado do package name para evitar rainbow tables simples
        val salted = "elion_mdm_salt_${password}_v1"
        val bytes = digest.digest(salted.toByteArray(Charsets.UTF_8))
        return bytes.joinToString("") { "%02x".format(it) }
    }

    private fun generateSessionToken(): String {
        val bytes = ByteArray(32)
        java.security.SecureRandom().nextBytes(bytes)
        return bytes.joinToString("") { "%02x".format(it) }
    }

    // ─── Result ───────────────────────────────────────────────────────────────

    sealed class AuthResult {
        object Success : AuthResult()
        data class Failed(val remainingAttempts: Int) : AuthResult()
        data class LockedOut(val remainingSeconds: Long) : AuthResult()
    }
}
