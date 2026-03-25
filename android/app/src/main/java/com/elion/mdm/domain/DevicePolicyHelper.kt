package com.elion.mdm.domain

import android.app.ActivityManager
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.os.UserManager
import android.util.Log
import com.elion.mdm.DeviceAdminReceiver

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

    private val admin: ComponentName = ComponentName(context, DeviceAdminReceiver::class.java)

    // ─── Verificações ─────────────────────────────────────────────────────────

    fun isDeviceOwner(): Boolean = dpm.isDeviceOwnerApp(context.packageName)

    fun isDeviceAdmin(): Boolean = dpm.isAdminActive(admin)

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

    fun lockNow(): Result<Unit> = runCatching {
        check(checkAdmin("lockNow")) { "Não é Device Admin" }
        dpm.lockNow()
        Log.i(TAG, "lockNow() executado")
    }

    // ─── Wipe ─────────────────────────────────────────────────────────────────

    fun wipeDevice(includeExternalStorage: Boolean = false): Result<Unit> = runCatching {
        check(checkDO("wipeDevice")) { "Não é Device Owner" }
        val flags = if (includeExternalStorage) DevicePolicyManager.WIPE_EXTERNAL_STORAGE else 0
        Log.w(TAG, "wipeData(flags=$flags) — FACTORY RESET INICIADO")
        dpm.wipeData(flags)
    }

    // ─── Camera ───────────────────────────────────────────────────────────────

    fun setCameraDisabled(disabled: Boolean): Result<Unit> = runCatching {
        check(checkAdmin("setCameraDisabled")) { "Não é Device Admin" }
        dpm.setCameraDisabled(admin, disabled)
        Log.i(TAG, "setCameraDisabled($disabled)")
    }

    fun isCameraDisabled(): Boolean = dpm.getCameraDisabled(admin)

    // ─── Status Bar ───────────────────────────────────────────────────────────

    fun setStatusBarDisabled(disabled: Boolean): Result<Unit> = runCatching {
        check(checkDO("setStatusBarDisabled")) { "Não é Device Owner" }
        dpm.setStatusBarDisabled(admin, disabled)
        Log.i(TAG, "setStatusBarDisabled($disabled)")
    }

    // ─── Keyguard ─────────────────────────────────────────────────────────────

    fun disableKeyguard(): Result<Unit> = runCatching {
        check(checkDO("disableKeyguard")) { "Não é Device Owner" }
        dpm.setKeyguardDisabled(admin, true)
        Log.i(TAG, "Keyguard DESATIVADO")
    }

    fun enableKeyguard(): Result<Unit> = runCatching {
        check(checkDO("enableKeyguard")) { "Não é Device Owner" }
        dpm.setKeyguardDisabled(admin, false)
        Log.i(TAG, "Keyguard REATIVADO")
    }

    // ─── Kiosk Mode (Lock Task) ───────────────────────────────────────────────

    fun setKioskPackages(packages: Array<String>): Result<Unit> = runCatching {
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
        check(checkDO("setLockTaskFeatures")) { "Não é Device Owner" }
        dpm.setLockTaskFeatures(admin, features)
        Log.i(TAG, "setLockTaskFeatures($features)")
    }

    fun isInLockTaskMode(): Boolean {
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        return am.lockTaskModeState != ActivityManager.LOCK_TASK_MODE_NONE
    }

    // ─── Screen Timeout ───────────────────────────────────────────────────────

    fun setScreenOffTimeout(timeoutMs: Long): Result<Unit> = runCatching {
        check(checkDO("setScreenOffTimeout")) { "Não é Device Owner" }
        dpm.setMaximumTimeToLock(admin, timeoutMs)
        Log.i(TAG, "setMaximumTimeToLock(${timeoutMs}ms)")
    }

    // ─── Password ─────────────────────────────────────────────────────────────

    fun setMinPasswordLength(length: Int): Result<Unit> = runCatching {
        check(checkAdmin("setMinPasswordLength")) { "Não é Device Admin" }
        dpm.setPasswordMinimumLength(admin, length)
        Log.i(TAG, "setPasswordMinimumLength($length)")
    }

    // ─── User Restrictions ────────────────────────────────────────────────────

    fun setFactoryResetDisabled(disabled: Boolean): Result<Unit> = runCatching {
        check(checkDO("setFactoryResetDisabled")) { "Não é Device Owner" }
        if (disabled) dpm.addUserRestriction(admin, UserManager.DISALLOW_FACTORY_RESET)
        else          dpm.clearUserRestriction(admin, UserManager.DISALLOW_FACTORY_RESET)
        Log.i(TAG, "DISALLOW_FACTORY_RESET=$disabled")
    }

    fun setSafeModeDisabled(disabled: Boolean): Result<Unit> = runCatching {
        check(checkDO("setSafeModeDisabled")) { "Não é Device Owner" }
        if (disabled) dpm.addUserRestriction(admin, UserManager.DISALLOW_SAFE_BOOT)
        else          dpm.clearUserRestriction(admin, UserManager.DISALLOW_SAFE_BOOT)
        Log.i(TAG, "DISALLOW_SAFE_BOOT=$disabled")
    }

    /**
     * Aplica TODAS as restrições de usuário para lockdown completo.
     * Impede: instalar/desinstalar apps, USB, modificar contas, adicionar usuários,
     * factory reset, safe mode, montar mídia física.
     */
    fun enableFullLockdown(): Result<Unit> = runCatching {
        check(checkDO("enableFullLockdown")) { "Não é Device Owner" }

        val restrictions = arrayOf(
            UserManager.DISALLOW_INSTALL_APPS,
            UserManager.DISALLOW_UNINSTALL_APPS,
            UserManager.DISALLOW_USB_FILE_TRANSFER,
            UserManager.DISALLOW_MODIFY_ACCOUNTS,
            UserManager.DISALLOW_ADD_USER,
            UserManager.DISALLOW_FACTORY_RESET,
            UserManager.DISALLOW_SAFE_BOOT,
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
        check(checkDO("disableFullLockdown")) { "Não é Device Owner" }

        val restrictions = arrayOf(
            UserManager.DISALLOW_INSTALL_APPS,
            UserManager.DISALLOW_UNINSTALL_APPS,
            UserManager.DISALLOW_USB_FILE_TRANSFER,
            UserManager.DISALLOW_MODIFY_ACCOUNTS,
            UserManager.DISALLOW_ADD_USER,
            UserManager.DISALLOW_FACTORY_RESET,
            UserManager.DISALLOW_SAFE_BOOT,
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
        check(checkDO("reboot")) { "Não é Device Owner" }
        dpm.reboot(admin)
        Log.i(TAG, "reboot() solicitado")
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
