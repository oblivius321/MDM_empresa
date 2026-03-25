package com.elion.mdm.launcher

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.ImageView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.elion.mdm.R
import com.elion.mdm.admin.AdminLoginActivity
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.domain.DevicePolicyHelper
import com.elion.mdm.security.KioskSecurityManager
import org.json.JSONArray

/**
 * KioskLauncherActivity — HOME app do launcher kiosk enterprise.
 *
 * Registrada no AndroidManifest com:
 *   <category android:name="android.intent.category.HOME"/>
 *   <category android:name="android.intent.category.DEFAULT"/>
 *
 * Quando configurada como launcher padrão, intercepta o botão Home do Android.
 * Em Lock Task Mode, o usuário fica preso nesta tela sem poder sair.
 *
 * Fluxo:
 *   1. onCreate → verifica se kiosk está ativo → startLockTask()
 *   2. Carrega apps permitidos → exibe grid
 *   3. ⋮ menu → AdminLoginActivity (NUNCA expõe settings diretamente)
 *   4. onBackPressed → bloqueado
 *   5. onPause/onStop → reclaim foreground se em kiosk
 */
class KioskLauncherActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "ElionKioskLauncher"

        fun launch(context: Context) {
            val intent = Intent(context, KioskLauncherActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
            }
            context.startActivity(intent)
        }
    }

    private lateinit var prefs: SecurePreferences
    private lateinit var dpm: DevicePolicyHelper
    private lateinit var securityManager: KioskSecurityManager

    private lateinit var rvApps: RecyclerView
    private lateinit var tvEmpty: TextView
    private lateinit var btnMenu: ImageView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_kiosk_launcher)

        prefs = SecurePreferences(this)
        dpm = DevicePolicyHelper(this)
        securityManager = KioskSecurityManager(this)

        bindViews()
        setupMenu()
        loadApps()
        enterKioskIfNeeded()
    }

    override fun onResume() {
        super.onResume()
        loadApps()  // Refresh on resume
        enterKioskIfNeeded()
        securityManager.startWatchdog()
    }

    override fun onPause() {
        super.onPause()
        // Se estamos em kiosk e a activity perdeu foco, reclaim
        if (prefs.isKioskEnabled && !isFinishing) {
            reclaimForeground()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        securityManager.destroy()
    }

    @Deprecated("Deprecated in API level 33")
    override fun onBackPressed() {
        // Bloquear Back em modo kiosk
        if (prefs.isKioskEnabled) {
            Log.d(TAG, "Back bloqueado em modo kiosk")
            return
        }
        super.onBackPressed()
    }

    // ─── Views ────────────────────────────────────────────────────────────────

    private fun bindViews() {
        rvApps = findViewById(R.id.rv_apps)
        tvEmpty = findViewById(R.id.tv_empty)
        btnMenu = findViewById(R.id.btn_menu)
    }

    private fun setupMenu() {
        btnMenu.setOnClickListener {
            // SEMPRE abrir login admin primeiro, NUNCA settings diretamente
            val intent = Intent(this, AdminLoginActivity::class.java)
            startActivity(intent)
        }
    }

    // ─── App Grid ─────────────────────────────────────────────────────────────

    private fun loadApps() {
        val allowedPackages = getAllowedPackages()

        if (allowedPackages.isEmpty()) {
            tvEmpty.visibility = View.VISIBLE
            rvApps.visibility = View.GONE
            return
        }

        tvEmpty.visibility = View.GONE
        rvApps.visibility = View.VISIBLE

        val apps = AllowedAppAdapter.loadApps(this, allowedPackages)

        val spanCount = if (resources.configuration.screenWidthDp >= 600) 6 else 4
        rvApps.layoutManager = GridLayoutManager(this, spanCount)
        rvApps.adapter = AllowedAppAdapter(this, apps) { appInfo ->
            launchApp(appInfo.packageName)
        }
    }

    private fun getAllowedPackages(): List<String> {
        return try {
            val json = prefs.allowedAppsJson
            val array = JSONArray(json)
            (0 until array.length()).map { array.getString(it) }
        } catch (e: Exception) {
            emptyList()
        }
    }

    private fun launchApp(packageName: String) {
        val intent = packageManager.getLaunchIntentForPackage(packageName) ?: return
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
    }

    // ─── Kiosk Lock Task ──────────────────────────────────────────────────────

    private fun enterKioskIfNeeded() {
        if (!prefs.isKioskEnabled) return
        if (!dpm.isDeviceOwner()) {
            Log.w(TAG, "Não é Device Owner — Lock Task não disponível")
            return
        }

        // Garantir que nosso pacote está na whitelist de Lock Task
        val currentPackages = dpm.getKioskPackages()
        if (!currentPackages.contains(packageName)) {
            dpm.setKioskPackages(currentPackages + packageName)
        }

        // Configurar features do Lock Task (lockdown total)
        dpm.setLockTaskFeatures(
            android.app.admin.DevicePolicyManager.LOCK_TASK_FEATURE_SYSTEM_INFO or
            android.app.admin.DevicePolicyManager.LOCK_TASK_FEATURE_GLOBAL_ACTIONS
        )

        // Entrar em Lock Task Mode
        if (!dpm.isInLockTaskMode()) {
            try {
                startLockTask()
                Log.i(TAG, "Lock Task Mode ATIVADO")
            } catch (e: Exception) {
                Log.e(TAG, "Falha ao entrar em Lock Task: ${e.message}")
            }
        }

        // Aplicar lockdown adicional
        dpm.setStatusBarDisabled(true)
        dpm.disableKeyguard()
        dpm.enableFullLockdown()
    }

    fun exitKiosk() {
        try {
            stopLockTask()
            Log.i(TAG, "Lock Task Mode DESATIVADO")
        } catch (e: Exception) {
            Log.e(TAG, "Falha ao sair de Lock Task: ${e.message}")
        }
        dpm.setStatusBarDisabled(false)
        dpm.enableKeyguard()
        dpm.disableFullLockdown()
        securityManager.stopWatchdog()
    }

    // ─── Reclaim Foreground ───────────────────────────────────────────────────

    private fun reclaimForeground() {
        val am = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        if (am.lockTaskModeState != ActivityManager.LOCK_TASK_MODE_NONE) {
            // Estamos em Lock Task, trazer de volta
            val intent = Intent(this, KioskLauncherActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
            }
            startActivity(intent)
        }
    }
}
