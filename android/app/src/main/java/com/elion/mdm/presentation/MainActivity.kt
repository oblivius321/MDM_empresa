package com.elion.mdm.presentation

import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.view.View
import android.widget.*
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.elion.mdm.R
import com.elion.mdm.system.DevMode
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

/**
 * MainActivity — UI mínima do agente MDM.
 *
 * Telas:
 *   • Não enrollado → formulário de enrollment (backend URL + bootstrap secret)
 *   • Enrollado     → painel de status (device_id, last sync, modo Device Owner)
 *
 * Não é necessária uma UI rica — o MDM é operado pelo administrador via dashboard web.
 * Esta tela serve apenas para o técnico configurar o dispositivo na primeira vez.
 */
class MainActivity : AppCompatActivity() {

    private val viewModel: MainViewModel by viewModels()

    private companion object {
        private val TOKEN_EXTRA_KEYS = arrayOf(
            "bootstrap_token",
            "bootstrap_secret",
            "enrollment_token"
        )
        private val BACKEND_URL_EXTRA_KEYS = arrayOf(
            "api_url",
            "backend_url"
        )
        private val ENROLLMENT_EXTRA_KEYS = TOKEN_EXTRA_KEYS + BACKEND_URL_EXTRA_KEYS + "profile_id"
    }

    // Views — enrollment
    private lateinit var enrollmentPanel   : View
    private lateinit var etBackendUrl      : EditText
    private lateinit var etBootstrapSecret : EditText
    private lateinit var btnEnroll         : Button
    private lateinit var tvEnrollError     : TextView

    // Views — status
    private lateinit var statusPanel       : View
    private lateinit var tvDeviceId        : TextView
    private lateinit var tvLastSync        : TextView
    private lateinit var tvDeviceOwner     : TextView
    private lateinit var tvCamera          : TextView
    private lateinit var tvKiosk           : TextView
    private lateinit var tvAllowedApps     : TextView
    private lateinit var tvPolicyMode      : TextView
    private lateinit var tvBackendStatus   : TextView
    private lateinit var tvControllerMessage: TextView
    private lateinit var btnRefresh        : Button
    private lateinit var btnManageApps     : Button
    private lateinit var btnEnableKiosk    : Button

    // Shared
    private lateinit var loadingOverlay    : View
    private lateinit var progressBar       : ProgressBar
    private lateinit var tvDevModeBanner   : TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        bindViews()
        setupDevModeWarning()
        observeState()
        
        // ADB/provisioning extras are one-shot. Normal app launch must wait for the
        // technician to type the current token and tap Enroll.
        handleAdbEnrollmentIntent(intent)

        btnEnroll.setOnClickListener { onEnrollClicked() }
        btnRefresh.setOnClickListener { viewModel.refreshStatus() }
        btnManageApps.setOnClickListener { showAllowedAppsDialog() }
        btnEnableKiosk.setOnClickListener { viewModel.enableKioskMode() }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleAdbEnrollmentIntent(intent)
    }

    // ─── Binding ──────────────────────────────────────────────────────────────

    private fun bindViews() {
        enrollmentPanel   = findViewById(R.id.enrollment_panel)
        etBackendUrl      = findViewById(R.id.et_backend_url)
        etBootstrapSecret = findViewById(R.id.et_bootstrap_secret)
        btnEnroll         = findViewById(R.id.btn_enroll)
        tvEnrollError     = findViewById(R.id.tv_enroll_error)

        statusPanel       = findViewById(R.id.status_panel)
        tvDeviceId        = findViewById(R.id.tv_device_id)
        tvLastSync        = findViewById(R.id.tv_last_sync)
        tvDeviceOwner     = findViewById(R.id.tv_device_owner)
        tvCamera          = findViewById(R.id.tv_camera)
        tvKiosk           = findViewById(R.id.tv_kiosk)
        tvAllowedApps     = findViewById(R.id.tv_allowed_apps)
        tvPolicyMode      = findViewById(R.id.tv_policy_mode)
        tvBackendStatus   = findViewById(R.id.tv_backend_status)
        tvControllerMessage = findViewById(R.id.tv_controller_message)
        btnRefresh        = findViewById(R.id.btn_refresh)
        btnManageApps     = findViewById(R.id.btn_manage_apps)
        btnEnableKiosk    = findViewById(R.id.btn_enable_kiosk)

        loadingOverlay    = findViewById(R.id.loading_overlay)
        progressBar       = findViewById(R.id.progress_bar)
        tvDevModeBanner   = findViewById(R.id.tv_dev_mode_banner)
    }

    private fun setupDevModeWarning() {
        if (!DevMode.isDevMode()) {
            tvDevModeBanner.visibility = View.GONE
            return
        }

        tvDevModeBanner.visibility = View.VISIBLE
        tvDevModeBanner.text = "DEV MODE - soft kiosk, sem lock de rede movel"
        DevMode.showLaunchToast(this)
    }

    // ─── Observação de estado ─────────────────────────────────────────────────

    private fun observeState() {
        lifecycleScope.launch {
            viewModel.uiState.collect { state ->
                loadingOverlay.visibility = if (state.isLoading) View.VISIBLE else View.GONE
                progressBar.visibility = if (state.isLoading) View.VISIBLE else View.GONE
                btnEnroll.isEnabled    = !state.isLoading
                btnRefresh.isEnabled   = !state.isLoading

                if (!state.errorMessage.isNullOrBlank()) {
                    if (state.errorMessage?.contains("404") == true) {
                        tvEnrollError.text = "${state.errorMessage}\nDica: use a URL do backend acessivel pelo Android, por exemplo http://192.168.25.227:8200, e nao a porta do frontend."
                    } else {
                        tvEnrollError.text = state.errorMessage
                    }
                    tvEnrollError.visibility = View.VISIBLE
                } else {
                    tvEnrollError.visibility = View.GONE
                }

                // --- Roteamento Baseado em Estado ---
                when (state.mdmState) {
                    com.elion.mdm.domain.MdmState.UNCONFIGURED, 
                    com.elion.mdm.domain.MdmState.ENROLLING -> {
                        enrollmentPanel.visibility = View.VISIBLE
                        statusPanel.visibility     = View.GONE
                    }
                    com.elion.mdm.domain.MdmState.ENROLLED -> {
                        enrollmentPanel.visibility = View.GONE
                        statusPanel.visibility     = View.VISIBLE
                        
                        val status = state.deviceStatus
                        if (status != null) {
                            renderStatus(status)
                            renderControllerMessage(state)
                            btnManageApps.isEnabled = !state.isLoading
                            btnEnableKiosk.isEnabled = !state.isLoading &&
                                !status.isKioskEnabled &&
                                (status.isDeviceOwner || com.elion.mdm.system.DevMode.isDevMode())
                        }
                    }
                    com.elion.mdm.domain.MdmState.KIOSK_ACTIVE -> {
                        // Se o app foi aberto e deveria estar em Kiosk, forçar redirecionamento
                        com.elion.mdm.launcher.KioskLauncherActivity.launch(this@MainActivity)
                        if (!com.elion.mdm.system.DevMode.isDevMode()) {
                            finish() // Fecha a main para não ficar por baixo do kiosk no modo PROD
                        }
                    }
                }
            }
        }
    }

    // ─── Actions ──────────────────────────────────────────────────────────────

    private fun handleAdbEnrollmentIntent(intent: Intent?): Boolean {
        if (intent == null) return false

        val token = firstExtra(intent, *TOKEN_EXTRA_KEYS)
        val backendUrl = firstExtra(intent, *BACKEND_URL_EXTRA_KEYS)
        val profileId = firstExtra(intent, "profile_id")

        if (token.isNullOrBlank() || backendUrl.isNullOrBlank()) {
            return false
        }

        etBackendUrl.setText(backendUrl)
        etBootstrapSecret.setText(token)
        clearEnrollmentIntentExtras(intent)
        viewModel.enroll(token, backendUrl, profileId)
        return true
    }

    private fun firstExtra(intent: Intent, vararg keys: String): String? {
        return keys.firstNotNullOfOrNull { key ->
            intent.getStringExtra(key)?.trim()?.takeIf { it.isNotBlank() }
        }
    }

    private fun clearEnrollmentIntentExtras(source: Intent) {
        val sanitized = Intent(source)
        ENROLLMENT_EXTRA_KEYS.forEach { sanitized.removeExtra(it) }
        setIntent(sanitized)
    }

    private fun onEnrollClicked() {
        val url    = etBackendUrl.text.toString().trim()
        val secret = etBootstrapSecret.text.toString().trim()

        if (url.isBlank() || secret.isBlank()) {
            tvEnrollError.text       = "Preencha todos os campos"
            tvEnrollError.visibility = View.VISIBLE
            return
        }

        viewModel.enroll(secret, url)
    }

    private fun showAllowedAppsDialog() {
        val intent = Intent(Intent.ACTION_MAIN).apply { addCategory(Intent.CATEGORY_LAUNCHER) }
        val resolveInfos = packageManager.queryIntentActivities(intent, 0)
        
        val installedApps = resolveInfos.map { it.activityInfo.applicationInfo }
            .filter { it.packageName != packageName }
            .distinctBy { it.packageName }
            .sortedBy { packageManager.getApplicationLabel(it).toString().lowercase(Locale.getDefault()) }

        if (installedApps.isEmpty()) {
            Toast.makeText(this, "No launchable apps found", Toast.LENGTH_SHORT).show()
            return
        }

        val currentAllowed = viewModel.uiState.value.deviceStatus
            ?.allowedPackages
            ?.toMutableSet()
            ?: mutableSetOf()

        val labels = installedApps
            .map { "${packageManager.getApplicationLabel(it)}\n${it.packageName}" }
            .toTypedArray()
        val checked = installedApps
            .map { currentAllowed.contains(it.packageName) }
            .toBooleanArray()

        AlertDialog.Builder(this)
            .setTitle("Allowed Kiosk Apps")
            .setMultiChoiceItems(labels, checked) { _, which, isChecked ->
                val pkg = installedApps[which].packageName
                if (isChecked) currentAllowed.add(pkg) else currentAllowed.remove(pkg)
            }
            .setPositiveButton("Save") { _, _ ->
                viewModel.saveAllowedKioskApps(currentAllowed.toList())
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    // ─── Render ───────────────────────────────────────────────────────────────

    private fun renderStatus(status: com.elion.mdm.domain.usecase.DeviceStatus) {
        tvDeviceId.text  = "Device ID: ${status.deviceId ?: "—"}"
        tvLastSync.text  = "Último sync: ${formatTimestamp(status.lastSyncMs)}"
        tvDeviceOwner.text = "Device Owner: ${if (status.isDeviceOwner) "✅ SIM" else "❌ NÃO"}"
        tvCamera.text    = "Câmera: ${if (status.isCameraDisabled) "🔴 Desativada" else "🟢 Ativa"}"
        tvKiosk.text     = buildString {
            append("Kiosk: ")
            append(
                when {
                    status.isKioskEnabled && status.isDevMode -> "Soft ativo (DEV)"
                    status.isKioskEnabled -> "Hard ativo"
                    else -> "Desativado"
                }
            )
            append(" | Lock Task: ")
            append(if (status.isLockTaskActive) "Ativo" else "Inativo")
        }
        tvAllowedApps.text = buildString {
            append("Allowed apps: ${status.allowedPackages.size}")
            if (status.kioskPackages.isNotEmpty()) {
                append(" | DPM packages: ${status.kioskPackages.size}")
            }
            if (!status.kioskTargetPackage.isNullOrBlank()) {
                append("\nTarget app: ${status.kioskTargetPackage}")
            }
        }
        tvPolicyMode.text = if (status.isDevMode) {
            "Policy mode: ${DevMode.softKioskSummary()}"
        } else {
            "Policy mode: PROD hard enforcement ativo quando a policy exigir."
        }
        tvBackendStatus.text = buildString {
            append("Backend: ")
            append(status.backendUrl.ifBlank { "não configurado" })
            append("\nRede: ")
            append(status.networkType.uppercase(Locale.getDefault()))
            append(" | WS: ")
            append(
                if (status.lastWsConnectedAt > 0L) {
                    "último OK ${formatTimestamp(status.lastWsConnectedAt)}"
                } else {
                    "sem conexão ainda"
                }
            )
            append(" | Reconnects: ${status.wsReconnectCount}")
            if (!status.lastErrorCode.isNullOrBlank()) {
                append("\nÚltimo erro: ${status.lastErrorCode}")
            }
        }
        btnEnableKiosk.text = "Enable Kiosk Mode"
    }

    private fun renderControllerMessage(state: MainViewModel.UiState) {
        val message = state.errorMessage ?: state.actionMessage
        if (message.isNullOrBlank()) {
            tvControllerMessage.visibility = View.GONE
            return
        }

        tvControllerMessage.text = message
        tvControllerMessage.setTextColor(
            if (state.errorMessage != null) Color.rgb(211, 47, 47) else Color.rgb(46, 125, 50)
        )
        tvControllerMessage.visibility = View.VISIBLE
    }

    private fun formatTimestamp(ms: Long): String {
        if (ms == 0L) return "nunca"
        return SimpleDateFormat("dd/MM/yyyy HH:mm:ss", Locale.getDefault()).format(Date(ms))
    }
}
