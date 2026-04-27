package com.elion.mdm.launcher

import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.ImageView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.elion.mdm.R

class AppSelectionActivity : AppCompatActivity() {

    private lateinit var rvApps: RecyclerView
    private lateinit var btnBack: ImageView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_app_selection)

        rvApps = findViewById(R.id.rv_apps_selection)
        btnBack = findViewById(R.id.btn_back)

        btnBack.setOnClickListener { finish() }

        setupAppGridSpacing()
        loadApps()
    }

    private fun loadApps() {
        val pm = packageManager
        
        // Pega todos os apps instalados que possuem uma interface que pode ser lançada
        val mainIntent = Intent(Intent.ACTION_MAIN, null).apply {
            addCategory(Intent.CATEGORY_LAUNCHER)
        }
        val resolveInfos = pm.queryIntentActivities(mainIntent, 0)

        val appsList = resolveInfos.mapNotNull { info ->
            val pkg = info.activityInfo.packageName
            // Exclui o proprio MDM para nao criar um loop de launcher
            if (pkg == packageName) return@mapNotNull null
            
            val appInfo = pm.getApplicationInfo(pkg, PackageManager.GET_META_DATA)
            AppInfo(
                packageName = pkg,
                label = pm.getApplicationLabel(appInfo).toString(),
                icon = pm.getApplicationIcon(appInfo)
            )
        }.sortedBy { it.label.lowercase() }

        rvApps.layoutManager = GridLayoutManager(this, calculateSpanCount())
        rvApps.adapter = AppSelectionAdapter(this, appsList) { selectedApp ->
            returnSelectedApp(selectedApp.packageName)
        }
    }

    private fun setupAppGridSpacing() {
        if (rvApps.itemDecorationCount == 0) {
            val spacingPx = (12 * resources.displayMetrics.density).toInt()
            rvApps.addItemDecoration(GridSpacingItemDecoration(spacingPx))
        }
    }

    private fun calculateSpanCount(): Int {
        val screenWidthDp = resources.configuration.screenWidthDp.takeIf { it > 0 } ?: 360
        return (screenWidthDp / 112).coerceIn(2, 5)
    }

    private fun returnSelectedApp(packageName: String) {
        val resultIntent = Intent().apply {
            putExtra("EXTRA_PACKAGE_NAME", packageName)
        }
        setResult(Activity.RESULT_OK, resultIntent)
        finish()
    }
}
