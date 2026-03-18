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

    fun enroll(bootstrapSecret: String, backendUrl: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)

            enrollUseCase(bootstrapSecret, backendUrl)
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
