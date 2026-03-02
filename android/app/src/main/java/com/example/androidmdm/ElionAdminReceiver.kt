package com.example.androidmdm

import android.app.admin.DeviceAdminReceiver
import android.content.Context
import android.content.Intent
import android.widget.Toast

class ElionAdminReceiver : DeviceAdminReceiver() {

    override fun onEnabled(context: Context, intent: Intent) {
        super.onEnabled(context, intent)
        Toast.makeText(context, "Elion MDM: Privilégios de Administrador Ativados!", Toast.LENGTH_LONG).show()
    }

    override fun onDisabled(context: Context, intent: Intent) {
        super.onDisabled(context, intent)
        Toast.makeText(context, "Elion MDM: Aviso: O MDM foi desativado.", Toast.LENGTH_LONG).show()
    }

    override fun onPasswordFailed(context: Context, intent: Intent) {
        super.onPasswordFailed(context, intent)
        Toast.makeText(context, "Elion MDM: Tentativa de senha incorreta!", Toast.LENGTH_SHORT).show()
    }

    override fun onPasswordSucceeded(context: Context, intent: Intent) {
        super.onPasswordSucceeded(context, intent)
        Toast.makeText(context, "Elion MDM: Login bem sucedido.", Toast.LENGTH_SHORT).show()
    }
}
