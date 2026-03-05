package com.example.androidmdm

import android.content.Context
import android.graphics.Color
import android.graphics.PixelFormat
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.TextView

class OverlayManager(private val context: Context) {
    private val windowManager = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    private var overlayView: View? = null

    fun showPersistentAlert(message: String) {
        if (overlayView != null) return // Já existe um overlay

        val layoutParams = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY, // Overlay critical
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
            WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON or
            WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED,
            PixelFormat.TRANSLUCENT
        )
        layoutParams.gravity = Gravity.TOP

        val layout = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#D32F2F")) // Vermelho Urgência
            setPadding(32, 64, 32, 32)
        }

        val textView = TextView(context).apply {
            text = "⚠️ ELION MDM ALERT\n$message"
            setTextColor(Color.WHITE)
            textSize = 18f
            gravity = Gravity.CENTER
        }

        layout.addView(textView)
        overlayView = layout

        try {
            windowManager.addView(overlayView, layoutParams)
        } catch (e: Exception) {
            android.util.Log.e("ElionMDM", "Erro ao desenhar Overlay (Perdeu permissão?): ${e.message}")
        }
    }

    fun removeAlert() {
        overlayView?.let {
            windowManager.removeView(it)
            overlayView = null
        }
    }
}
