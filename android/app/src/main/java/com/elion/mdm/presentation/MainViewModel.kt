package com.elion.mdm.presentation

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.elion.mdm.data.local.SecurePreferences
import com.elion.mdm.domain.DevicePolicyHelper
import com.elion.mdm.domain.usecase.DeviceStatus
import com.elion.mdm.domain.usecase.EnrollDeviceUseCase
import com.elion.mdm.domain.usecase.GetDeviceStatusUseCase
import com.elion.mdm.system.DevMode
import com.elion.mdm.system.KioskManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.json.JSONArray

/**
 * MainViewModel — gerencia o estado da tela principal (enrollment + status).
 *
 * Usa AndroidViewModel para acessar o Context sem vazar a Activity.
 * Expõe StateFlow para observação reativa na UI (Compose ou View).
 */
class MainViewModel(app: Application) : AndroidViewModel(app) {

    private val enrollUseCase     = EnrollDeviceUseCase(app)
    private val statusUseCase     = GetDeviceStatusUseCase(app)
    private val kioskManager      = KioskManager(app)
    private val prefs             = SecurePreferences(app)
    private val dpm               = DevicePolicyHelper(app)

    // ─── Estado da UI ─────────────────────────────────────────────────────────

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        refreshStatus()
    }

    fun getCurrentState(): com.elion.mdm.domain.MdmState = prefs.mdmState

    // ─── Actions ──────────────────────────────────────────────────────────────

    fun enroll(bootstrapToken: String, backendUrl: String, profileId: String? = null) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)

            enrollUseCase.enroll(bootstrapToken, backendUrl, profileId)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(
                        isLoading    = false,
                        deviceStatus = statusUseCase(),
                        actionMessage = null
                    )
                }
                .onFailure { err ->
                    _uiState.value = _uiState.value.copy(
                        isLoading    = false,
                        deviceStatus = statusUseCase(),
                        errorMessage = err.message ?: "Erro desconhecido no enrollment",
                        actionMessage = null
                    )
                }
        }
    }

    fun enableKioskMode() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null, actionMessage = null)

            runCatching {
                check(DevMode.isDevMode() || dpm.isDeviceOwner()) {
                    "Kiosk mode requires Device Owner"
                }

                kioskManager.enableKiosk(readAllowedPackages())
                prefs.mdmState = com.elion.mdm.domain.MdmState.KIOSK_ACTIVE
            }.onSuccess {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    deviceStatus = statusUseCase(),
                    actionMessage = "Kiosk mode enabled"
                )
            }.onFailure { err ->
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    deviceStatus = statusUseCase(),
                    errorMessage = err.message ?: "Failed to enable kiosk mode"
                )
            }
        }
    }

    fun saveAllowedKioskApps(packages: List<String>) {
        viewModelScope.launch {
            val cleanPackages = packages
                .map { it.trim() }
                .filter { it.isNotBlank() }
                .distinct()

            writeAllowedPackages(cleanPackages)

            if (prefs.isKioskEnabled) {
                kioskManager.enableKiosk(cleanPackages)
            }

            _uiState.value = _uiState.value.copy(
                deviceStatus = statusUseCase(),
                errorMessage = null,
                actionMessage = "${cleanPackages.size} allowed app(s) saved"
            )
        }
    }

    fun refreshStatus() {
        _uiState.value = _uiState.value.copy(
            deviceStatus = statusUseCase(),
            mdmState = prefs.mdmState,
            errorMessage = null,
            actionMessage = null
        )
    }

    private fun readAllowedPackages(): List<String> {
        return try {
            val array = JSONArray(prefs.allowedAppsJson)
            (0 until array.length()).map { array.getString(it) }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun writeAllowedPackages(packages: List<String>) {
        val array = JSONArray()
        packages.forEach { array.put(it) }
        prefs.allowedAppsJson = array.toString()
    }

    // ─── UI State ─────────────────────────────────────────────────────────────

    data class UiState(
        val isLoading    : Boolean      = false,
        val errorMessage : String?      = null,
        val actionMessage: String?      = null,
        val deviceStatus : DeviceStatus? = null,
        val mdmState     : com.elion.mdm.domain.MdmState = com.elion.mdm.domain.MdmState.UNCONFIGURED
    )
}
