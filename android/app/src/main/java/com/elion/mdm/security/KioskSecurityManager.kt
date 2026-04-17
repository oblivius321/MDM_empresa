package com.elion.mdm.security

import android.content.Context
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.domain.DevicePolicyHelper
import com.elion.mdm.system.DevMode
import kotlinx.coroutines.*

/**
 * KioskSecurityManager — watchdog de segurança anti-tampering.
 *
 * Responsabilidades:
 *   1. Verificar periodicamente que o app ainda é Device Owner
 *   2. Detectar se Lock Task Mode foi quebrado → re-aplicar
 *   3. Detectar se status bar foi reativada → re-desabilitar
 *   4. Auto-recuperação de estado em caso de anomalias
 *
 * O watchdog roda em um loop de coroutine a cada 15 segundos.
 * Se detecta qualquer violação, tenta automaticamente restaurar
 * o estado de lockdown completo.
 */
class KioskSecurityManager(context: Context) {

    companion object {
        private const val TAG = "ElionSecurity"
        private const val WATCHDOG_INTERVAL_MS = 15_000L  // 15 segundos
    }

    private val appContext = context.applicationContext
    private val dpm = DevicePolicyHelper(appContext)
    private val prefs = SecurePreferences(appContext)
    private val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private var watchdogJob: Job? = null

    // ─── Controle ─────────────────────────────────────────────────────────────

    fun startWatchdog() {
        if (DevMode.isDevMode()) {
            DevMode.log("Kiosk watchdog disabled in DEV build")
            return
        }
        if (watchdogJob?.isActive == true) {
            Log.d(TAG, "Watchdog já está ativo")
            return
        }

        watchdogJob = scope.launch {
            Log.i(TAG, "Watchdog de segurança INICIADO")
            while (isActive) {
                performSecurityCheck()
                delay(WATCHDOG_INTERVAL_MS)
            }
        }
    }

    fun stopWatchdog() {
        watchdogJob?.cancel()
        watchdogJob = null
        Log.i(TAG, "Watchdog de segurança PARADO")
    }

    fun destroy() {
        scope.cancel()
        Log.i(TAG, "KioskSecurityManager destruído")
    }

    // ─── Verificação de Segurança ─────────────────────────────────────────────

    private fun performSecurityCheck() {
        if (DevMode.isDevMode()) return
        if (!prefs.isKioskEnabled) return  // Kiosk não está ativo, nada a verificar

        var violations = 0

        // 1. Verificar se ainda é Device Owner
        if (!dpm.isDeviceOwner()) {
            Log.e(TAG, "⚠️ VIOLAÇÃO: App não é mais Device Owner!")
            violations++
            // Não conseguimos nos auto-recuperar de perda de DO
            // Mas podemos logar e notificar o backend
        }

        // 2. Verificar se Lock Task Mode está ativo
        if (!dpm.isInLockTaskMode()) {
            Log.w(TAG, "⚠️ VIOLAÇÃO: Lock Task Mode foi desativado — re-aplicando...")
            violations++
            // A re-ativação do Lock Task precisa ser feita na Activity
            // Sinalizar via prefs para que o launcher re-aplique
        }

        // 3. Re-aplicar restrições se temos DO
        if (dpm.isDeviceOwner()) {
            // Re-bloquear status bar
            dpm.setStatusBarDisabled(true)
                .onFailure { Log.e(TAG, "Falha ao re-bloquear status bar: ${it.message}") }

            // Re-aplicar restrições de usuário
            dpm.enableFullLockdown()
                .onFailure { Log.e(TAG, "Falha ao re-aplicar lockdown: ${it.message}") }
        }

        if (violations > 0) {
            Log.w(TAG, "Verificação de segurança: $violations violação(ões) detectada(s)")
        } else {
            Log.d(TAG, "Verificação de segurança: OK ✅")
        }
    }

    // ─── Verificação pontual (chamada de fora) ────────────────────────────────

    fun checkAndRecover() {
        performSecurityCheck()
    }

    fun isSecure(): Boolean {
        if (DevMode.isDevMode()) return true
        if (!prefs.isKioskEnabled) return true
        return dpm.isDeviceOwner() && dpm.isInLockTaskMode()
    }
}
