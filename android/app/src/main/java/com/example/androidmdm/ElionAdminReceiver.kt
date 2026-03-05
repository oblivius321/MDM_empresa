package com.example.androidmdm

import android.app.admin.DeviceAdminReceiver
import android.content.Context
import android.content.Intent
import android.widget.Toast
import android.util.Log

class ElionAdminReceiver : DeviceAdminReceiver() {

    override fun onEnabled(context: Context, intent: Intent) {
        super.onEnabled(context, intent)
        Toast.makeText(context, "Elion MDM: Privilégios de Administrador Ativados!", Toast.LENGTH_LONG).show()
    }

    override fun onDisabled(context: Context, intent: Intent) {
        super.onDisabled(context, intent)
        Toast.makeText(context, "Elion MDM: Aviso: O MDM foi desativado.", Toast.LENGTH_LONG).show()
    }

    override fun onDisableRequested(context: Context, intent: Intent): CharSequence {
        Log.w("ElionMDM", "Alerta de Segurança: Tentativa de desativar o Administrador do Dispositivo!")
        return "Elion MDM: Aviso de Segurança. A remoção deste perfil corporativo é rastreada e reportada ao painel central."
    }

    override fun onPasswordFailed(context: Context, intent: Intent) {
        super.onPasswordFailed(context, intent)
        Log.e("ElionMDM", "Alerta de Segurança: Falha ao inserir senha de bloqueio.")
        Toast.makeText(context, "Elion MDM: Tentativa de senha incorreta rastreada!", Toast.LENGTH_SHORT).show()
    }

    override fun onPasswordSucceeded(context: Context, intent: Intent) {
        super.onPasswordSucceeded(context, intent)
        Toast.makeText(context, "Elion MDM: Login bem sucedido.", Toast.LENGTH_SHORT).show()
    }
}
