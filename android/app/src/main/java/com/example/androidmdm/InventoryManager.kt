package com.example.androidmdm

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.BatteryManager
import android.os.Build
import android.os.Environment
import android.os.StatFs
data class DeviceInventory(
    val batteryLevel: Float,
    val isCharging: Boolean,
    val availableStorage: Long,
    val installedPackages: List<String>
)

class InventoryManager(private val context: Context) {

    fun getInventory(): DeviceInventory {
        return DeviceInventory(
            batteryLevel = getBatteryLevel(),
            isCharging = isCharging(),
            availableStorage = getFreeDiskSpaceMb(),
            installedPackages = getInstalledApps()
        )
    }

    private fun getBatteryLevel(): Float {
        val intentFilter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        val batteryStatus: Intent? = context.registerReceiver(null, intentFilter)
        val level: Int = batteryStatus?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale: Int = batteryStatus?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        return if (level == -1 || scale == -1) 0f else (level * 100 / scale.toFloat())
    }

    private fun isCharging(): Boolean {
        val intentFilter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        val batteryStatus: Intent? = context.registerReceiver(null, intentFilter)
        val status: Int = batteryStatus?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        return status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL
    }

    private fun getFreeDiskSpaceMb(): Long {
        val stat = StatFs(Environment.getDataDirectory().path)
        val bytesAvailable = stat.blockSizeLong * stat.availableBlocksLong
        return bytesAvailable / (1024 * 1024)
    }

    private fun getInstalledApps(): List<String> {
        val appsList = mutableListOf<String>()
        val pm = context.packageManager
        val packages = pm.getInstalledApplications(PackageManager.GET_META_DATA)
        for (packageInfo in packages) {
            if ((packageInfo.flags and android.content.pm.ApplicationInfo.FLAG_SYSTEM) == 0) {
                appsList.add(packageInfo.packageName)
            }
        }
        return appsList
    }
}
