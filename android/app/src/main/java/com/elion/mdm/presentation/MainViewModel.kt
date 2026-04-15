package com.elion.mdm.presentation

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.elion.mdm.domain.usecase.DeviceStatus
import com.elion.mdm.domain.usecase.EnrollDeviceUseCase
import com.elion.mdm.domain.usecase.GetDeviceStatusUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * MainViewModel — gerencia o estado da tela principal (enrollment + status).
 *
 * Usa AndroidViewModel para acessar o Context sem vazar a Activity.
 * Expõe StateFlow para observação reativa na UI (Compose ou View).
 */
class MainViewModel(app: Application) : AndroidViewModel(app) {

    private val enrollUseCase     = EnrollDeviceUseCase(app)
    private val statusUseCase     = GetDeviceStatusUseCase(app)

    // ─── Estado da UI ─────────────────────────────────────────────────────────

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        refreshStatus()
    }

    // ─── Actions ──────────────────────────────────────────────────────────────

    fun enroll(bootstrapSecret: String, backendUrl: String, profileId: String? = null) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)

            enrollUseCase.enroll(bootstrapSecret, backendUrl, profileId)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(
                        isLoading    = false,
                        deviceStatus = statusUseCase()
                    )
                }
                .onFailure { err ->
                    _uiState.value = _uiState.value.copy(
                        isLoading    = false,
                        errorMessage = err.message ?: "Erro desconhecido no enrollment"
                    )
                }
        }
    }

    /**
     * Verifica se há metadados de bootstrapping pendentes (vidos do QR Code)
     * e dispara o enrollment sem intervenção humana se possível.
     */
    fun checkAutoEnrollment() {
        viewModelScope.launch {
            val info = com.elion.mdm.system.MDMStateMachine.getStateInfo(getApplication())
            if (info.state == com.elion.mdm.system.MDMState.INIT || info.state == com.elion.mdm.system.MDMState.REGISTERING) {
                val profileId = info.metadata["profile_id"]
                val apiUrl = info.metadata["api_url"]
                val bootstrapToken = info.metadata["bootstrap_token"]
                
                if (!apiUrl.isNullOrBlank() && !bootstrapToken.isNullOrBlank()) {
                    android.util.Log.i("ElionViewModel", "Auto-Enrollment disparado para profile: ${profileId ?: "token-bound"}")
                    enroll(bootstrapToken, apiUrl, profileId)
                }
            }
        }
    }

    fun refreshStatus() {
        _uiState.value = _uiState.value.copy(deviceStatus = statusUseCase())
    }

    // ─── UI State ─────────────────────────────────────────────────────────────

    data class UiState(
        val isLoading    : Boolean      = false,
        val errorMessage : String?      = null,
        val deviceStatus : DeviceStatus? = null
    )
}
