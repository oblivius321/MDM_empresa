package com.elion.mdm.presentation

import android.os.Bundle
import android.view.View
import android.widget.*
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.elion.mdm.R
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
    private lateinit var btnRefresh        : Button

    // Shared
    private lateinit var progressBar       : ProgressBar

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        bindViews()
        observeState()

        btnEnroll.setOnClickListener { onEnrollClicked() }
        btnRefresh.setOnClickListener { viewModel.refreshStatus() }
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
        btnRefresh        = findViewById(R.id.btn_refresh)

        progressBar       = findViewById(R.id.progress_bar)
    }

    // ─── Observação de estado ─────────────────────────────────────────────────

    private fun observeState() {
        lifecycleScope.launch {
            viewModel.uiState.collect { state ->
                progressBar.visibility = if (state.isLoading) View.VISIBLE else View.GONE
                btnEnroll.isEnabled    = !state.isLoading

                if (!state.errorMessage.isNullOrBlank()) {
                    tvEnrollError.text       = state.errorMessage
                    tvEnrollError.visibility = View.VISIBLE
                } else {
                    tvEnrollError.visibility = View.GONE
                }

                val status = state.deviceStatus
                if (status != null && status.isEnrolled) {
                    enrollmentPanel.visibility = View.GONE
                    statusPanel.visibility     = View.VISIBLE
                    renderStatus(status)
                } else {
                    enrollmentPanel.visibility = View.VISIBLE
                    statusPanel.visibility     = View.GONE
                }
            }
        }
    }

    // ─── Actions ──────────────────────────────────────────────────────────────

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

    // ─── Render ───────────────────────────────────────────────────────────────

    private fun renderStatus(status: com.elion.mdm.domain.usecase.DeviceStatus) {
        tvDeviceId.text  = "Device ID: ${status.deviceId ?: "—"}"
        tvLastSync.text  = "Último sync: ${formatTimestamp(status.lastSyncMs)}"
        tvDeviceOwner.text = "Device Owner: ${if (status.isDeviceOwner) "✅ SIM" else "❌ NÃO"}"
        tvCamera.text    = "Câmera: ${if (status.isCameraDisabled) "🔴 Desativada" else "🟢 Ativa"}"
        tvKiosk.text     = if (status.kioskPackages.isEmpty())
            "Kiosk: Desativado"
        else
            "Kiosk: ${status.kioskPackages.joinToString()}"
    }

    private fun formatTimestamp(ms: Long): String {
        if (ms == 0L) return "nunca"
        return SimpleDateFormat("dd/MM/yyyy HH:mm:ss", Locale.getDefault()).format(Date(ms))
    }
}
