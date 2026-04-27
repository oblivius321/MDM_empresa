package com.elion.mdm.launcher

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.elion.mdm.R

/**
 * AllowedAppAdapter — adapter para o grid de aplicativos permitidos no kiosk.
 *
 * Exibe ícone + label de cada app permitido.
 * Ao clicar, lança o app via packageManager.getLaunchIntentForPackage().
 */
class AllowedAppAdapter(
    private val context: Context,
    private val apps: List<AppInfo>,
    private val onAppClick: (AppInfo) -> Unit
) : RecyclerView.Adapter<AllowedAppAdapter.AppViewHolder>() {

    inner class AppViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val icon: ImageView = view.findViewById(R.id.app_icon)
        val label: TextView = view.findViewById(R.id.app_label)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): AppViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_allowed_app, parent, false)
        return AppViewHolder(view)
    }

    override fun onBindViewHolder(holder: AppViewHolder, position: Int) {
        val app = apps[position]
        holder.label.text = app.label
        holder.icon.setImageDrawable(app.icon)
        holder.itemView.setOnClickListener { onAppClick(app) }
    }

    override fun getItemCount() = apps.size

    companion object {
        /**
         * Carrega a lista de AppInfo para os pacotes permitidos.
         * Ignora pacotes que não estejam instalados.
         */
        fun loadApps(context: Context, allowedPackages: List<String>): List<AppInfo> {
            val pm = context.packageManager
            return allowedPackages.mapNotNull { pkg ->
                try {
                    val appInfo = pm.getApplicationInfo(pkg, 0)
                    val label = pm.getApplicationLabel(appInfo).toString()
                    val icon = pm.getApplicationIcon(appInfo)
                    AppInfo(pkg, label, icon)
                } catch (e: PackageManager.NameNotFoundException) {
                    null  // App não instalado, ignorar
                }
            }.sortedBy { it.label.lowercase() }
        }
    }
}
