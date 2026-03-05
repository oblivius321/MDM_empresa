package com.example.androidmdm

import android.app.usage.UsageStats
import android.app.usage.UsageStatsManager
import android.content.Context
import android.util.Log

class ActivityMonitor(private val context: Context) {
    private val usageStatsManager = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager

    fun getForegroundApp(): String {
        val endTime = System.currentTimeMillis()
        val startTime = endTime - 1000 * 60 // Último 1 minuto

        val usageStats = usageStatsManager.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, startTime, endTime)
        
        var currentApp = "Unknown"
        var lastTimeUsed = 0L

        for (stats in usageStats) {
            if (stats.lastTimeUsed > lastTimeUsed) {
                lastTimeUsed = stats.lastTimeUsed
                currentApp = stats.packageName
            }
        }
        return currentApp
    }

    fun getDailyUsageStats(): Map<String, Long> {
        val usageMap = mutableMapOf<String, Long>()
        val endTime = System.currentTimeMillis()
        val startTime = endTime - 1000 * 60 * 60 * 24 // Últimas 24h

        val usageStats = usageStatsManager.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, startTime, endTime)

        for (stats in usageStats) {
             if (stats.totalTimeInForeground > 0) {
                 usageMap[stats.packageName] = stats.totalTimeInForeground
             }
        }
        
        Log.d("ElionMDM", "Atividade monitorada em ${usageMap.size} apps.")
        return usageMap
    }
}
