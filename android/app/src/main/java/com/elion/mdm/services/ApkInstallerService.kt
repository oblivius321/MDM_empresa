package com.elion.mdm.services

import android.app.IntentService
import android.content.Intent
import android.util.Log

class ApkInstallerService : IntentService("ApkInstallerService") {
    companion object {
        const val EXTRA_APK_URL = "extra_apk_url"
    }

    override fun onHandleIntent(intent: Intent?) {
        val url = intent?.getStringExtra(EXTRA_APK_URL)
        if (url != null) {
            Log.i("ApkInstallerService", "Installing APK from $url")
            // Minimal implementation as requested
        }
    }
}
