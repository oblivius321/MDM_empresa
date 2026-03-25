package com.elion.mdm.system

import android.app.admin.DevicePolicyManager
import android.content.Context
import android.content.Intent
import android.util.Log
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.domain.DevicePolicyHelper
import com.elion.mdm.launcher.KioskLauncherActivity
import org.json.JSONArray

/**
 * KioskManager — orquestrador central do modo kiosk.
 *
 * Responsável por coordenar:
 *   1. Ativação do kiosk (salvar config → set Lock Task packages → restrições → launch)
 *   2. Desativação (stopLockTask → limpar restrições → restaurar launcher normal)
 *   3. Re-aplicação após boot/recovery
 *
 * Usado por: CommandHandler, AdminPanelActivity, BootReceiver
 */
class KioskManager(private val context: Context) {

    companion object {
        private const val TAG = "ElionKioskManager"
    }

    private val dpm = DevicePolicyHelper(context)
    private val prefs = SecurePreferences(context)

    // ─── Ativar Kiosk ─────────────────────────────────────────────────────────

    /**
     * Ativa o modo kiosk completo:
     *   1. Salva lista de apps permitidos
     *   2. Configura Lock Task packages (nosso app + apps permitidos)
     *   3. Configura features do Lock Task (lockdown quase total)
     *   4. Aplica restrições de usuário
     *   5. Desabilita status bar e keyguard
     *   6. Lança KioskLauncherActivity
     */
    fun enableKiosk(allowedPackages: List<String> = emptyList()) {
        Log.i(TAG, "Ativando modo kiosk...")

        if (!dpm.isDeviceOwner()) {
            Log.e(TAG, "ERRO: App não é Device Owner — kiosk não pode ser ativado")
            return
        }

        // 1. Salvar config
        prefs.isKioskEnabled = true
        if (allowedPackages.isNotEmpty()) {
            val array = JSONArray()
            allowedPackages.forEach { array.put(it) }
            prefs.allowedAppsJson = array.toString()
        }

        // 2. Lock Task packages = nosso app + apps permitidos
        val packages = (allowedPackages + context.packageName).distinct().toTypedArray()
        dpm.setKioskPackages(packages)
            .onFailure { Log.e(TAG, "Falha ao definir Lock Task packages: ${it.message}") }

        // 3. Lock Task features (sistema limitado — apenas relógio/bateria + power menu)
        dpm.setLockTaskFeatures(
            DevicePolicyManager.LOCK_TASK_FEATURE_SYSTEM_INFO or
            DevicePolicyManager.LOCK_TASK_FEATURE_GLOBAL_ACTIONS
        ).onFailure { Log.e(TAG, "Falha ao definir Lock Task features: ${it.message}") }

        // 4. Restrições de usuário (lockdown completo)
        dpm.enableFullLockdown()
            .onFailure { Log.e(TAG, "Falha ao aplicar lockdown: ${it.message}") }

        // 5. Status bar + keyguard
        dpm.setStatusBarDisabled(true)
            .onFailure { Log.e(TAG, "Falha ao bloquear status bar: ${it.message}") }
        dpm.disableKeyguard()
            .onFailure { Log.e(TAG, "Falha ao desabilitar keyguard: ${it.message}") }

        // 6. Lançar launcher
        KioskLauncherActivity.launch(context)

        Log.i(TAG, "Modo kiosk ATIVADO com ${packages.size} pacote(s) permitido(s)")
    }

    // ─── Desativar Kiosk ──────────────────────────────────────────────────────

    /**
     * Desativa o modo kiosk:
     *   1. Limpa Lock Task packages
     *   2. Remove restrições de usuário
     *   3. Reativa status bar e keyguard
     *   4. Atualiza estado persistido
     */
    fun disableKiosk() {
        Log.i(TAG, "Desativando modo kiosk...")

        prefs.isKioskEnabled = false

        if (dpm.isDeviceOwner()) {
            // Limpar Lock Task packages
            dpm.setKioskPackages(emptyArray())
                .onFailure { Log.e(TAG, "Falha ao limpar Lock Task packages: ${it.message}") }

            // Remover restrições
            dpm.disableFullLockdown()
                .onFailure { Log.e(TAG, "Falha ao remover lockdown: ${it.message}") }

            // Reativar status bar + keyguard
            dpm.setStatusBarDisabled(false)
                .onFailure { Log.e(TAG, "Falha ao desbloquear status bar: ${it.message}") }
            dpm.enableKeyguard()
                .onFailure { Log.e(TAG, "Falha ao reativar keyguard: ${it.message}") }
        }

        Log.i(TAG, "Modo kiosk DESATIVADO")
    }

    // ─── Estado ───────────────────────────────────────────────────────────────

    fun isKioskActive(): Boolean = prefs.isKioskEnabled

    // ─── Re-aplicar (para boot/recovery) ──────────────────────────────────────

    /**
     * Chamado pelo BootReceiver e pelo KioskSecurityManager.
     * Se o kiosk deveria estar ativo mas não está, re-aplica.
     */
    fun reapplyIfNeeded() {
        if (!prefs.isKioskEnabled) return

        Log.i(TAG, "Re-aplicando modo kiosk após boot/recovery...")

        val allowedPackages = try {
            val array = JSONArray(prefs.allowedAppsJson)
            (0 until array.length()).map { array.getString(it) }
        } catch (e: Exception) {
            emptyList()
        }

        enableKiosk(allowedPackages)
    }
}
