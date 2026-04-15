package com.elion.mdm.provisioning

import android.app.Activity
import android.app.admin.DevicePolicyManager
import android.content.Intent
import android.os.Bundle
import android.os.PersistableBundle
import android.util.Log

/**
 * Selects fully managed provisioning for Android 12+ admin-integrated setup.
 */
class ProvisioningModeActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handleProvisioningModeRequest()
    }

    private fun handleProvisioningModeRequest() {
        val provisioningMode = chooseProvisioningMode()
        val result = Intent().apply {
            putExtra(DevicePolicyManager.EXTRA_PROVISIONING_MODE, provisioningMode)
            putExtra(DevicePolicyManager.EXTRA_PROVISIONING_SKIP_EDUCATION_SCREENS, true)

            getAdminExtras()?.let {
                putExtra(DevicePolicyManager.EXTRA_PROVISIONING_ADMIN_EXTRAS_BUNDLE, it)
            }
        }

        Log.i(TAG, "Provisioning mode selected: $provisioningMode")
        setResult(RESULT_OK, result)
        finish()
    }

    private fun chooseProvisioningMode(): Int {
        val allowedModes = getAllowedProvisioningModes()
        val fullyManaged = DevicePolicyManager.PROVISIONING_MODE_FULLY_MANAGED_DEVICE
        val managedProfile = DevicePolicyManager.PROVISIONING_MODE_MANAGED_PROFILE

        return when {
            allowedModes.isEmpty() -> fullyManaged
            fullyManaged in allowedModes -> fullyManaged
            managedProfile in allowedModes -> managedProfile
            else -> allowedModes.first()
        }
    }

    private fun getAllowedProvisioningModes(): List<Int> {
        return try {
            intent.getIntegerArrayListExtra(
                DevicePolicyManager.EXTRA_PROVISIONING_ALLOWED_PROVISIONING_MODES
            )?.toList()
                ?: intent.getIntArrayExtra(
                    DevicePolicyManager.EXTRA_PROVISIONING_ALLOWED_PROVISIONING_MODES
                )?.toList()
                ?: emptyList()
        } catch (e: RuntimeException) {
            Log.w(TAG, "Unable to read allowed provisioning modes", e)
            emptyList()
        }
    }

    private fun getAdminExtras(): PersistableBundle? {
        return try {
            intent.getParcelableExtra(DevicePolicyManager.EXTRA_PROVISIONING_ADMIN_EXTRAS_BUNDLE)
        } catch (e: RuntimeException) {
            Log.w(TAG, "Unable to read admin extras", e)
            null
        }
    }

    private companion object {
        private const val TAG = "ElionProvisioningMode"
    }
}
