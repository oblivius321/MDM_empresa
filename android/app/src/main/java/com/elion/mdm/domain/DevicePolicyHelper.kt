package com.elion.mdm.domain

import android.app.ActivityManager
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.os.UserManager
import android.util.Log
import com.elion.mdm.AdminReceiver
import com.elion.mdm.system.DevMode

/**
 * DevicePolicyHelper — abstração sobre DevicePolicyManager (DPM).
 *
 * Centraliza todas as operações que requerem privilégio de Device Owner.
 * Cada método verifica se o app é DO antes de executar.
 */
class DevicePolicyHelper(private val context: Context) {

    companion object {
        private const val TAG = "ElionDPM"
    }

    private val dpm: DevicePolicyManager =
        context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager

    private val admin: ComponentName = ComponentName(context, AdminReceiver::class.java)

    // ─── Verificações ─────────────────────────────────────────────────────────

    fun isDeviceOwner(): Boolean = runCatching {
        dpm.isDeviceOwnerApp(context.packageName)
    }.getOrDefault(false)

    /**
     * Tenta obter o IMEI. Requer Device Owner no Android 10+.
     */
    fun getImei(): String? = runCatching {
        if (isDeviceOwner()) {
            val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as android.telephony.TelephonyManager
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                tm.imei ?: tm.deviceId
            } else {
                @Suppress("DEPRECATION")
                tm.deviceId
            }
        } else {
            null
        }
    }.getOrNull()

    /**
     * Tenta obter o Serial Number. Requer Device Owner no Android 10+.
     */
    fun getSerialNumber(): String? = runCatching {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            if (isDeviceOwner()) android.os.Build.getSerial() else null
        } else {
            @Suppress("DEPRECATION")
            android.os.Build.SERIAL
        }
    }.getOrNull()

    fun isDeviceAdmin(): Boolean = runCatching {
        dpm.isAdminActive(admin)
    }.getOrDefault(false)

    private fun checkDO(action: String): Boolean {
        return isDeviceOwner().also {
            if (!it) Log.e(TAG, "[$action] FALHOU — app não é Device Owner")
        }
    }

    private fun checkAdmin(action: String): Boolean {
        return isDeviceAdmin().also {
            if (!it) Log.e(TAG, "[$action] FALHOU — app não é Device Admin")
        }
    }

    // ─── Lock ─────────────────────────────────────────────────────────────────

    private fun blockDevEnforcement(action: String): Boolean {
        if (!DevMode.isDevMode()) return false
        DevMode.blockDangerousPolicy(action)
        return true
    }

    private fun skipDevRecoveryWithoutOwner(action: String): Boolean {
        if (!DevMode.isDevMode() || isDeviceOwner()) return false
        DevMode.log("Ignoring recovery policy without Device Owner: $action")
        return true
    }

    fun lockNow(): Result<Unit> = runCatching {
        if (blockDevEnforcement("lockNow")) return@runCatching
        check(checkAdmin("lockNow")) { "Não é Device Admin" }
        dpm.lockNow()
        Log.i(TAG, "lockNow() executado")
    }

    // ─── Wipe ─────────────────────────────────────────────────────────────────

    fun wipeDevice(includeExternalStorage: Boolean = false): Result<Unit> = runCatching {
        if (blockDevEnforcement("wipeData")) return@runCatching
        check(checkDO("wipeDevice")) { "Não é Device Owner" }
        val flags = if (includeExternalStorage) DevicePolicyManager.WIPE_EXTERNAL_STORAGE else 0
        Log.w(TAG, "wipeData(flags=$flags) — FACTORY RESET INICIADO")
        dpm.wipeData(flags)
    }

    // ─── Camera ───────────────────────────────────────────────────────────────

    fun setCameraDisabled(disabled: Boolean): Result<Unit> = runCatching {
        if (disabled && blockDevEnforcement("setCameraDisabled(true)")) return@runCatching
        check(checkAdmin("setCameraDisabled")) { "Não é Device Admin" }
        dpm.setCameraDisabled(admin, disabled)
        Log.i(TAG, "setCameraDisabled($disabled)")
    }

    fun isCameraDisabled(): Boolean = runCatching {
        if (isDeviceAdmin()) dpm.getCameraDisabled(admin) else false
    }.getOrDefault(false)

    // ─── Status Bar ───────────────────────────────────────────────────────────

    fun setStatusBarDisabled(disabled: Boolean): Result<Unit> = runCatching {
        if (disabled && blockDevEnforcement("setStatusBarDisabled(true)")) return@runCatching
        if (!disabled && skipDevRecoveryWithoutOwner("setStatusBarDisabled(false)")) return@runCatching
        check(checkDO("setStatusBarDisabled")) { "Não é Device Owner" }
        dpm.setStatusBarDisabled(admin, disabled)
        Log.i(TAG, "setStatusBarDisabled($disabled)")
    }

    // ─── Keyguard ─────────────────────────────────────────────────────────────

    fun disableKeyguard(): Result<Unit> = runCatching {
        if (blockDevEnforcement("setKeyguardDisabled(true)")) return@runCatching
        check(checkDO("disableKeyguard")) { "Não é Device Owner" }
        dpm.setKeyguardDisabled(admin, true)
        Log.i(TAG, "Keyguard DESATIVADO")
    }

    fun enableKeyguard(): Result<Unit> = runCatching {
        if (skipDevRecoveryWithoutOwner("setKeyguardDisabled(false)")) return@runCatching
        check(checkDO("enableKeyguard")) { "Não é Device Owner" }
        dpm.setKeyguardDisabled(admin, false)
        Log.i(TAG, "Keyguard REATIVADO")
    }

    // ─── Kiosk Mode (Lock Task) ───────────────────────────────────────────────

    fun setKioskPackages(packages: Array<String>): Result<Unit> = runCatching {
        if (packages.isNotEmpty() && blockDevEnforcement("setLockTaskPackages")) return@runCatching
        if (packages.isEmpty() && skipDevRecoveryWithoutOwner("clearLockTaskPackages")) return@runCatching
        check(checkDO("setKioskPackages")) { "Não é Device Owner" }
        dpm.setLockTaskPackages(admin, packages)
        Log.i(TAG, "setLockTaskPackages: ${packages.joinToString()}")
    }

    fun getKioskPackages(): Array<String> =
        if (isDeviceOwner()) dpm.getLockTaskPackages(admin) else emptyArray()

    fun isKioskAllowed(pkg: String): Boolean = getKioskPackages().contains(pkg)

    /**
     * Configura quais elementos do sistema ficam visíveis no Lock Task Mode.
     * Por padrão: NENHUM (lockdown total).
     *
     * Flags disponíveis:
     *   LOCK_TASK_FEATURE_NONE            = 0
     *   LOCK_TASK_FEATURE_SYSTEM_INFO     = 1  (relógio, bateria)
     *   LOCK_TASK_FEATURE_NOTIFICATIONS   = 2
     *   LOCK_TASK_FEATURE_HOME            = 4
     *   LOCK_TASK_FEATURE_OVERVIEW        = 8  (recents)
     *   LOCK_TASK_FEATURE_GLOBAL_ACTIONS  = 16 (power menu)
     *   LOCK_TASK_FEATURE_KEYGUARD        = 32
     */
    fun setLockTaskFeatures(features: Int = DevicePolicyManager.LOCK_TASK_FEATURE_NONE): Result<Unit> = runCatching {
        if (blockDevEnforcement("setLockTaskFeatures($features)")) return@runCatching
        check(checkDO("setLockTaskFeatures")) { "Não é Device Owner" }
        dpm.setLockTaskFeatures(admin, features)
        Log.i(TAG, "setLockTaskFeatures($features)")
    }

    fun isInLockTaskMode(): Boolean = runCatching {
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        am.lockTaskModeState != ActivityManager.LOCK_TASK_MODE_NONE
    }.getOrDefault(false)

    // ─── Screen Timeout ───────────────────────────────────────────────────────

    fun setScreenOffTimeout(timeoutMs: Long): Result<Unit> = runCatching {
        if (blockDevEnforcement("setMaximumTimeToLock")) return@runCatching
        check(checkDO("setScreenOffTimeout")) { "Não é Device Owner" }
        dpm.setMaximumTimeToLock(admin, timeoutMs)
        Log.i(TAG, "setMaximumTimeToLock(${timeoutMs}ms)")
    }

    // ─── Password ─────────────────────────────────────────────────────────────

    fun setApplicationHidden(packageName: String, hidden: Boolean): Result<Unit> = runCatching {
        if (hidden && blockDevEnforcement("setApplicationHidden($packageName, true)")) return@runCatching
        if (!hidden && skipDevRecoveryWithoutOwner("setApplicationHidden($packageName, false)")) return@runCatching
        check(checkDO("setApplicationHidden")) { "Nao e Device Owner" }
        dpm.setApplicationHidden(admin, packageName, hidden)
        Log.i(TAG, "setApplicationHidden($packageName, hidden=$hidden)")
    }

    fun setMinPasswordLength(length: Int): Result<Unit> = runCatching {
        if (blockDevEnforcement("setPasswordMinimumLength")) return@runCatching
        check(checkAdmin("setMinPasswordLength")) { "Não é Device Admin" }
        dpm.setPasswordMinimumLength(admin, length)
        Log.i(TAG, "setPasswordMinimumLength($length)")
    }

    // ─── User Restrictions ────────────────────────────────────────────────────

    fun setRestriction(key: String, disabled: Boolean): Result<Unit> {
        return when (key) {
            "camera", "camera_disabled" -> setCameraDisabled(disabled)
            "status_bar", "status_bar_disabled" -> setStatusBarDisabled(disabled)
            "factory_reset", "factory_reset_disabled" -> setFactoryResetDisabled(disabled)
            "safe_mode", "safe_mode_disabled" -> setSafeModeDisabled(disabled)
            "usb_debug", "usb_debug_disabled" -> setUserRestriction(UserManager.DISALLOW_DEBUGGING_FEATURES, disabled)
            "usb_file_transfer", "usb_file_transfer_disabled" -> setUserRestriction(UserManager.DISALLOW_USB_FILE_TRANSFER, disabled)
            "install_apps", "install_apps_disabled" -> setUserRestriction(UserManager.DISALLOW_INSTALL_APPS, disabled)
            "uninstall_apps", "uninstall_apps_disabled" -> setUserRestriction(UserManager.DISALLOW_UNINSTALL_APPS, disabled)
            "install_unknown_sources", "install_unknown_sources_disabled" -> setUserRestriction(UserManager.DISALLOW_INSTALL_UNKNOWN_SOURCES, disabled)
            "add_user", "add_user_disabled" -> setUserRestriction(UserManager.DISALLOW_ADD_USER, disabled)
            "modify_accounts", "modify_accounts_disabled" -> setUserRestriction(UserManager.DISALLOW_MODIFY_ACCOUNTS, disabled)
            else -> runCatching {
                Log.w(TAG, "Restricao desconhecida ignorada: $key=$disabled")
            }
        }
    }

    private fun setUserRestriction(restriction: String, disabled: Boolean): Result<Unit> = runCatching {
        if (disabled && blockDevEnforcement("addUserRestriction($restriction)")) return@runCatching
        if (!disabled && skipDevRecoveryWithoutOwner("clearUserRestriction($restriction)")) return@runCatching
        check(checkDO("setUserRestriction:$restriction")) { "Nao e Device Owner" }
        if (disabled) dpm.addUserRestriction(admin, restriction)
        else dpm.clearUserRestriction(admin, restriction)
        Log.i(TAG, "$restriction=$disabled")
    }

    fun setFactoryResetDisabled(disabled: Boolean): Result<Unit> = runCatching {
        if (disabled && blockDevEnforcement("DISALLOW_FACTORY_RESET")) return@runCatching
        if (!disabled && skipDevRecoveryWithoutOwner("clear DISALLOW_FACTORY_RESET")) return@runCatching
        check(checkDO("setFactoryResetDisabled")) { "Não é Device Owner" }
        if (disabled) dpm.addUserRestriction(admin, UserManager.DISALLOW_FACTORY_RESET)
        else          dpm.clearUserRestriction(admin, UserManager.DISALLOW_FACTORY_RESET)
        Log.i(TAG, "DISALLOW_FACTORY_RESET=$disabled")
    }

    fun setSafeModeDisabled(disabled: Boolean): Result<Unit> = runCatching {
        if (disabled && blockDevEnforcement("DISALLOW_SAFE_BOOT")) return@runCatching
        if (!disabled && skipDevRecoveryWithoutOwner("clear DISALLOW_SAFE_BOOT")) return@runCatching
        check(checkDO("setSafeModeDisabled")) { "Não é Device Owner" }
        if (disabled) dpm.addUserRestriction(admin, UserManager.DISALLOW_SAFE_BOOT)
        else          dpm.clearUserRestriction(admin, UserManager.DISALLOW_SAFE_BOOT)
        Log.i(TAG, "DISALLOW_SAFE_BOOT=$disabled")
    }

    /**
     * Remove explicitamente as restrições que podem travar o desenvolvedor "fora" do aparelho.
     * Útil durante a fase de desenvolvimento para garantir que botões de Hard Reset funcionem.
     */
    fun clearSafetyRestrictions(): Result<Unit> = runCatching {
        if (skipDevRecoveryWithoutOwner("clearSafetyRestrictions")) return@runCatching
        check(checkDO("clearSafetyRestrictions")) { "Não é Device Owner" }
        dpm.clearUserRestriction(admin, UserManager.DISALLOW_FACTORY_RESET)
        dpm.clearUserRestriction(admin, UserManager.DISALLOW_SAFE_BOOT)
        Log.i(TAG, "Restrições de segurança (Reset/SafeBoot) LIMPAS para modo DEV")
    }

    /**
     * Aplica TODAS as restrições de usuário para lockdown completo.
     * Impede: instalar/desinstalar apps, USB, modificar contas, adicionar usuários,
     * factory reset, safe mode, montar mídia física.
     */
    fun enableFullLockdown(): Result<Unit> = runCatching {
        if (blockDevEnforcement("enableFullLockdown")) return@runCatching
        check(checkDO("enableFullLockdown")) { "Não é Device Owner" }

        val restrictions = arrayOf(
            UserManager.DISALLOW_INSTALL_APPS,
            UserManager.DISALLOW_UNINSTALL_APPS,
            UserManager.DISALLOW_USB_FILE_TRANSFER,
            UserManager.DISALLOW_MODIFY_ACCOUNTS,
            UserManager.DISALLOW_ADD_USER,
            // UserManager.DISALLOW_FACTORY_RESET,  // Removido para modo DEV
            // UserManager.DISALLOW_SAFE_BOOT,     // Removido para modo DEV
            UserManager.DISALLOW_DEBUGGING_FEATURES,
            UserManager.DISALLOW_MOUNT_PHYSICAL_MEDIA,
            UserManager.DISALLOW_CONFIG_MOBILE_NETWORKS,
        )

        restrictions.forEach { restriction ->
            dpm.addUserRestriction(admin, restriction)
        }
        Log.i(TAG, "Full lockdown APLICADO (${restrictions.size} restrições)")
    }

    /**
     * Remove TODAS as restrições de lockdown.
     */
    fun disableFullLockdown(): Result<Unit> = runCatching {
        if (skipDevRecoveryWithoutOwner("disableFullLockdown")) return@runCatching
        check(checkDO("disableFullLockdown")) { "Não é Device Owner" }

        val restrictions = arrayOf(
            UserManager.DISALLOW_INSTALL_APPS,
            UserManager.DISALLOW_UNINSTALL_APPS,
            UserManager.DISALLOW_USB_FILE_TRANSFER,
            UserManager.DISALLOW_MODIFY_ACCOUNTS,
            UserManager.DISALLOW_ADD_USER,
            UserManager.DISALLOW_FACTORY_RESET,
            UserManager.DISALLOW_SAFE_BOOT,
            UserManager.DISALLOW_DEBUGGING_FEATURES,
            UserManager.DISALLOW_MOUNT_PHYSICAL_MEDIA,
            UserManager.DISALLOW_CONFIG_MOBILE_NETWORKS,
        )

        restrictions.forEach { restriction ->
            dpm.clearUserRestriction(admin, restriction)
        }
        Log.i(TAG, "Full lockdown REMOVIDO")
    }

    // ─── Reboot ───────────────────────────────────────────────────────────────

    fun reboot(): Result<Unit> = runCatching {
        if (blockDevEnforcement("reboot")) return@runCatching
        check(checkDO("reboot")) { "Não é Device Owner" }
        dpm.reboot(admin)
        Log.i(TAG, "reboot() solicitado")
    }

    fun removeDeviceOwner(): Result<Unit> = runCatching {
        check(checkDO("removeDeviceOwner")) { "Nao e Device Owner" }
        Log.w(TAG, "clearDeviceOwnerApp(${context.packageName})")
        dpm.clearDeviceOwnerApp(context.packageName)
    }

    // ─── Apply Full Policy ────────────────────────────────────────────────────

    fun applyPolicy(
        cameraDisabled: Boolean,
        statusBarDisabled: Boolean,
        minPasswordLength: Int,
        screenTimeoutSeconds: Int
    ) {
        setCameraDisabled(cameraDisabled)
            .onFailure { Log.e(TAG, "câmera: ${it.message}") }
        setStatusBarDisabled(statusBarDisabled)
            .onFailure { Log.e(TAG, "statusBar: ${it.message}") }
        setMinPasswordLength(minPasswordLength)
            .onFailure { Log.e(TAG, "passwordLength: ${it.message}") }
        setScreenOffTimeout(screenTimeoutSeconds * 1000L)
            .onFailure { Log.e(TAG, "screenTimeout: ${it.message}") }

        Log.i(TAG, "Policy aplicada: camera=$cameraDisabled, statusBar=$statusBarDisabled, " +
                   "pwd=$minPasswordLength, timeout=${screenTimeoutSeconds}s")
    }
}
