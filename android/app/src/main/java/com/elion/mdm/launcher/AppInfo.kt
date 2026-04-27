package com.elion.mdm.launcher

import android.graphics.drawable.Drawable

/**
 * AppInfo — Modelo compartilhado para representar um aplicativo no sistema Elion.
 */
data class AppInfo(
    val packageName: String,
    val label: String,
    val icon: Drawable?
)
