package com.elion.mdm.domain

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.os.UserManager
import android.util.Log
import com.elion.mdm.AdminReceiver

/**
 * DevicePolicyHelper — abstração sobre DevicePolicyManager (DPM).
 *
 * Centraliza todas as operações que requerem privilégio de Device Owner.
 * Cada método verifica se o app é DO antes de executar, evitando
 * SecurityException em ambientes onde o app foi degradado.
 *
 * ─── Resumo de privilégios necessários ───────────────────────────────────────
 * • lockNow()              → Device Admin (mínimo)
 * • wipeData(flags extras) → Device Owner
 * • setLockTaskPackages()  → Device Owner (Kiosk Mode)
 * • setStatusBarDisabled() → Device Owner
 * • setCameraDisabled()    → Device Admin (escopo global requer DO)
 * • reboot()               → Device Owner (API 24+)
 * • addUserRestriction()   → Device Owner
 */
class DevicePolicyHelper(private val context: Context) {

    companion object {
        private const val TAG = "ElionDPM"
    }

    private val dpm: DevicePolicyManager =
        context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager

    private val admin: ComponentName = ComponentName(context, AdminReceiver::class.java)

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

    /**
     * AÇÃO IRREVERSÍVEL — apaga todos os dados do dispositivo (factory reset).
     * includeExternalStorage = true também limpa o SD Card.
     */
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

    /**
     * Desabilita a status bar (notificações + quick settings).
     * Essencial em Kiosk Mode para impedir o usuário de acessar as configurações.
     * Requer: Device Owner.
     */
    fun setStatusBarDisabled(disabled: Boolean): Result<Unit> = runCatching {
        check(checkDO("setStatusBarDisabled")) { "Não é Device Owner" }
        dpm.setStatusBarDisabled(admin, disabled)
        Log.i(TAG, "setStatusBarDisabled($disabled)")
    }

    // ─── Kiosk Mode (Lock Task) ───────────────────────────────────────────────

    /**
     * Define quais pacotes podem entrar em Lock Task Mode (Kiosk).
     * Após configurar, a Activity alvo chama startLockTask() e o usuário
     * fica preso no app sem conseguir sair pelo botão Home ou Recents.
     * Requer: Device Owner.
     */
    fun setKioskPackages(packages: Array<String>): Result<Unit> = runCatching {
        check(checkDO("setKioskPackages")) { "Não é Device Owner" }
        dpm.setLockTaskPackages(admin, packages)
        Log.i(TAG, "setLockTaskPackages: ${packages.joinToString()}")
    }

    fun getKioskPackages(): Array<String> =
        if (isDeviceOwner()) dpm.getLockTaskPackages(admin) else emptyArray()

    fun isKioskAllowed(pkg: String): Boolean = getKioskPackages().contains(pkg)

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

    /** Impede factory reset manual via Settings. */
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

    // ─── Reboot ───────────────────────────────────────────────────────────────

    /** Reinicia o dispositivo remotamente. Requer DO + API 24+. */
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
