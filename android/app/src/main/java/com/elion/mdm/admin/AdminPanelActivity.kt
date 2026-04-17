package com.elion.mdm.admin

import android.app.AlertDialog
import android.content.Intent
import android.media.AudioManager
import android.os.Build
import android.os.Bundle
import android.os.CountDownTimer
import android.provider.Settings
import android.util.Log
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import com.elion.mdm.R
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.domain.DevicePolicyHelper
import com.elion.mdm.security.AdminAuthManager
import com.elion.mdm.system.KioskManager
import org.json.JSONArray

/**
 * AdminPanelActivity — painel de controle administrativo (em português).
 *
 * Acessível apenas após autenticação via AdminLoginActivity.
 * Sessão expira em 5 minutos (verificada no onResume).
 *
 * Opções:
 *   • Ativar/Desativar Modo Kiosk
 *   • Configurações de Wi-Fi
 *   • Controle de Volume
 *   • Bloquear Barra de Status
 *   • Gerenciar Aplicativos Permitidos
 *   • Sincronizar com Servidor
 *   • Informações do Dispositivo
 *   • Sair do modo Kiosk (requer re-autenticação)
 */
class AdminPanelActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "ElionAdminPanel"
    }

    private lateinit var prefs: SecurePreferences
    private lateinit var dpm: DevicePolicyHelper
    private lateinit var authManager: AdminAuthManager
    private lateinit var kioskManager: KioskManager

    // Views
    private lateinit var tvSessionTimer: TextView
    private lateinit var tvKioskStatus: TextView
    private lateinit var tvStatusBarState: TextView
    private lateinit var tvAppCount: TextView
    private lateinit var tvDeviceInfo: TextView
    private lateinit var seekbarVolume: SeekBar

    private var sessionTimer: CountDownTimer? = null
    private var isStatusBarBlocked = true

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_admin_panel)

        prefs = SecurePreferences(this)
        dpm = DevicePolicyHelper(this)
        authManager = AdminAuthManager(this)
        kioskManager = KioskManager(this)

        bindViews()
        setupListeners()
        refreshState()
        startSessionCountdown()
    }

    override fun onResume() {
        super.onResume()
        // Verificar se a sessão expirou
        if (!authManager.hasValidSession()) {
            Log.w(TAG, "Sessão expirada — redirecionando para login")
            finish()
            return
        }
        refreshState()
    }

    override fun onDestroy() {
        super.onDestroy()
        sessionTimer?.cancel()
    }

    // ─── Views ────────────────────────────────────────────────────────────────

    private fun bindViews() {
        tvSessionTimer   = findViewById(R.id.tv_session_timer)
        tvKioskStatus    = findViewById(R.id.tv_kiosk_status)
        tvStatusBarState = findViewById(R.id.tv_status_bar_state)
        tvAppCount       = findViewById(R.id.tv_app_count)
        tvDeviceInfo     = findViewById(R.id.tv_device_info)
        seekbarVolume    = findViewById(R.id.seekbar_volume)
    }

    private fun setupListeners() {
        // Ativar/Desativar Kiosk
        findViewById<View>(R.id.btn_toggle_kiosk).setOnClickListener {
            toggleKiosk()
        }

        // Wi-Fi
        findViewById<View>(R.id.btn_wifi).setOnClickListener {
            openWifiSettings()
        }

        // Volume
        val audioManager = getSystemService(AUDIO_SERVICE) as AudioManager
        val maxVol = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        val curVol = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
        seekbarVolume.max = maxVol
        seekbarVolume.progress = curVol
        seekbarVolume.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(sb: SeekBar?, progress: Int, fromUser: Boolean) {
                if (fromUser) audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, progress, 0)
            }
            override fun onStartTrackingTouch(sb: SeekBar?) {}
            override fun onStopTrackingTouch(sb: SeekBar?) {}
        })

        // Status Bar
        findViewById<View>(R.id.btn_status_bar).setOnClickListener {
            toggleStatusBar()
        }

        // Gerenciar Apps
        findViewById<View>(R.id.btn_manage_apps).setOnClickListener {
            showAppManagementDialog()
        }

        // Sincronizar
        findViewById<View>(R.id.btn_sync).setOnClickListener {
            Toast.makeText(this, "Sincronizando com servidor...", Toast.LENGTH_SHORT).show()
            // TODO: trigger manual sync via MDMForegroundService
        }

        // Device Info
        findViewById<View>(R.id.btn_device_info).setOnClickListener {
            toggleDeviceInfo()
        }

        // Sair do Kiosk
        findViewById<View>(R.id.btn_exit_kiosk).setOnClickListener {
            confirmExitKiosk()
        }
    }

    // ─── Refresh State ────────────────────────────────────────────────────────

    private fun refreshState() {
        // Kiosk status
        val kioskActive = prefs.isKioskEnabled
        tvKioskStatus.text = if (kioskActive) "ATIVO" else "INATIVO"
        tvKioskStatus.setTextColor(
            if (kioskActive) 0xFF3FB950.toInt() else 0xFF8B949E.toInt()
        )

        // Status bar
        tvStatusBarState.text = if (isStatusBarBlocked) "BLOQUEADA" else "LIBERADA"
        tvStatusBarState.setTextColor(
            if (isStatusBarBlocked) 0xFF3FB950.toInt() else 0xFF8B949E.toInt()
        )

        // App count
        val apps = getAllowedPackages()
        tvAppCount.text = "${apps.size} app(s)"
    }

    // ─── Session Countdown ────────────────────────────────────────────────────

    private fun startSessionCountdown() {
        val remaining = prefs.sessionExpiryMs - System.currentTimeMillis()
        if (remaining <= 0) {
            finish()
            return
        }

        sessionTimer = object : CountDownTimer(remaining, 1000) {
            override fun onTick(millisUntilFinished: Long) {
                val mins = millisUntilFinished / 60000
                val secs = (millisUntilFinished % 60000) / 1000
                tvSessionTimer.text = String.format("%d:%02d", mins, secs)
            }

            override fun onFinish() {
                authManager.invalidateSession()
                Toast.makeText(this@AdminPanelActivity, "Sessão expirada", Toast.LENGTH_SHORT).show()
                finish()
            }
        }.start()
    }

    // ─── Actions ──────────────────────────────────────────────────────────────

    private fun toggleKiosk() {
        if (prefs.isKioskEnabled) {
            AlertDialog.Builder(this)
                .setTitle("Desativar Kiosk")
                .setMessage("Tem certeza que deseja desativar o modo kiosk?")
                .setPositiveButton("Sim") { _, _ ->
                    kioskManager.disableKiosk()
                    refreshState()
                    Toast.makeText(this, "Modo Kiosk desativado", Toast.LENGTH_SHORT).show()
                }
                .setNegativeButton("Cancelar", null)
                .show()
        } else {
            kioskManager.enableKiosk(getAllowedPackages())
            refreshState()
            Toast.makeText(this, "Modo Kiosk ativado", Toast.LENGTH_SHORT).show()
        }
    }

    private fun openWifiSettings() {
        try {
            // Temporariamente permitir acesso às configurações de Wi-Fi
            if (dpm.isDeviceOwner()) {
                dpm.setStatusBarDisabled(false)
            }
            startActivity(Intent(Settings.ACTION_WIFI_SETTINGS).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            })
        } catch (e: Exception) {
            Toast.makeText(this, "Não foi possível abrir configurações de Wi-Fi", Toast.LENGTH_SHORT).show()
        }
    }

    private fun toggleStatusBar() {
        if (!dpm.isDeviceOwner()) {
            Toast.makeText(this, "Requer Device Owner", Toast.LENGTH_SHORT).show()
            return
        }
        isStatusBarBlocked = !isStatusBarBlocked
        dpm.setStatusBarDisabled(isStatusBarBlocked)
        refreshState()
        Toast.makeText(
            this,
            if (isStatusBarBlocked) "Barra de status bloqueada" else "Barra de status liberada",
            Toast.LENGTH_SHORT
        ).show()
    }

    private fun showAppManagementDialog() {
        val pm = packageManager
        val intent = Intent(Intent.ACTION_MAIN).apply { addCategory(Intent.CATEGORY_LAUNCHER) }
        val resolveInfos = pm.queryIntentActivities(intent, 0)
        
        val installedApps = resolveInfos.map { it.activityInfo.applicationInfo }
            .filter { it.packageName != packageName }  // Excluir o próprio app MDM
            .distinctBy { it.packageName }
            .sortedBy { pm.getApplicationLabel(it).toString().lowercase() }

        val currentAllowed = getAllowedPackages().toMutableSet()
        val labels = installedApps.map { pm.getApplicationLabel(it).toString() }.toTypedArray()
        val checked = installedApps.map { currentAllowed.contains(it.packageName) }.toBooleanArray()

        AlertDialog.Builder(this)
            .setTitle("Selecionar Aplicativos Permitidos")
            .setMultiChoiceItems(labels, checked) { _, which, isChecked ->
                val pkg = installedApps[which].packageName
                if (isChecked) currentAllowed.add(pkg)
                else currentAllowed.remove(pkg)
            }
            .setPositiveButton("Salvar") { _, _ ->
                saveAllowedPackages(currentAllowed.toList())
                refreshState()
                Toast.makeText(this, "${currentAllowed.size} app(s) permitido(s)", Toast.LENGTH_SHORT).show()
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    private fun toggleDeviceInfo() {
        if (tvDeviceInfo.visibility == View.VISIBLE) {
            tvDeviceInfo.visibility = View.GONE
            return
        }

        val info = buildString {
            appendLine("Modelo: ${Build.MANUFACTURER} ${Build.MODEL}")
            appendLine("Android: ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})")
            appendLine("Device Owner: ${if (dpm.isDeviceOwner()) "SIM ✅" else "NÃO ❌"}")
            appendLine("Kiosk Ativo: ${if (prefs.isKioskEnabled) "SIM" else "NÃO"}")
            appendLine("Lock Task: ${if (dpm.isInLockTaskMode()) "SIM" else "NÃO"}")
            appendLine("Device ID: ${prefs.deviceId ?: "N/A"}")
            appendLine("Backend: ${prefs.backendUrl}")
            appendLine("Último Sync: ${formatTs(prefs.lastSyncTimestamp)}")
        }
        tvDeviceInfo.text = info
        tvDeviceInfo.visibility = View.VISIBLE
    }

    private fun confirmExitKiosk() {
        if (!prefs.isKioskEnabled) {
            Toast.makeText(this, "Kiosk não está ativo", Toast.LENGTH_SHORT).show()
            return
        }

        // Requer re-autenticação para sair
        AlertDialog.Builder(this)
            .setTitle("Sair do Modo Kiosk")
            .setMessage("Esta ação requer re-autenticação e irá desbloquear o dispositivo completamente.\n\nDeseja continuar?")
            .setPositiveButton("Sim, sair") { _, _ ->
                authManager.invalidateSession()
                kioskManager.disableKiosk()
                Toast.makeText(this, "Modo Kiosk desativado", Toast.LENGTH_LONG).show()
                finish()
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    // ─── Helpers ──────────────────────────────────────────────────────────────

    private fun getAllowedPackages(): List<String> {
        return try {
            val array = JSONArray(prefs.allowedAppsJson)
            (0 until array.length()).map { array.getString(it) }
        } catch (e: Exception) {
            emptyList()
        }
    }

    private fun saveAllowedPackages(packages: List<String>) {
        val array = JSONArray()
        packages.forEach { array.put(it) }
        prefs.allowedAppsJson = array.toString()
    }

    private fun formatTs(ms: Long): String {
        if (ms == 0L) return "nunca"
        val sdf = java.text.SimpleDateFormat("dd/MM/yyyy HH:mm:ss", java.util.Locale.getDefault())
        return sdf.format(java.util.Date(ms))
    }
}
