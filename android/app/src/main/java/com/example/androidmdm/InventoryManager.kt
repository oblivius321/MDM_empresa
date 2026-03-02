package com.example.androidmdm

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.BatteryManager
import android.os.Build
import android.os.Environment
import android.os.StatFs
import org.json.JSONArray
import org.json.JSONObject

class InventoryManager(private val context: Context) {

    fun getInventoryJson(): JSONObject {
        val inventory = JSONObject()
        inventory.put("battery_level", getBatteryLevel())
        inventory.put("free_disk_space_mb", getFreeDiskSpaceMb())
        inventory.put("android_version", Build.VERSION.RELEASE)
        inventory.put("installed_apps", getInstalledApps())
        return inventory
    }

    private fun getBatteryLevel(): Float {
        val intentFilter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        val batteryStatus: Intent? = context.registerReceiver(null, intentFilter)
        val level: Int = batteryStatus?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale: Int = batteryStatus?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        return if (level == -1 || scale == -1) 0f else (level * 100 / scale.toFloat())
    }

    private fun getFreeDiskSpaceMb(): Long {
        val stat = StatFs(Environment.getDataDirectory().path)
        val bytesAvailable = stat.blockSizeLong * stat.availableBlocksLong
        return bytesAvailable / (1024 * 1024)
    }

    private fun getInstalledApps(): JSONArray {
        val appsArray = JSONArray()
        val pm = context.packageManager
        val packages = pm.getInstalledApplications(PackageManager.GET_META_DATA)
        for (packageInfo in packages) {
            // Filtrar apenas aplicativos instalados pelo usuário (não os do sistema)
            if ((packageInfo.flags and android.content.pm.ApplicationInfo.FLAG_SYSTEM) == 0) {
                appsArray.put(packageInfo.packageName)
            }
        }
        return appsArray
    }
}
