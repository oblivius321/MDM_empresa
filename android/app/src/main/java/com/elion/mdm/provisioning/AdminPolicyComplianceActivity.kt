package com.elion.mdm.provisioning

import android.app.Activity
import android.os.Bundle
import android.util.Log

/**
 * Acknowledges Android 12+ admin policy compliance during fully managed setup.
 */
class AdminPolicyComplianceActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Log.i(TAG, "Provisioning compliance action completed: ${intent.action}")
        setResult(RESULT_OK, intent)
        finish()
    }

    private companion object {
        private const val TAG = "ElionPolicyCompliance"
    }
}
