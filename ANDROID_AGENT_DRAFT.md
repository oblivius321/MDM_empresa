# 📱 Esboço do Android Agent (Device Owner) - Kotlin

Para que seu aplicativo funcione como um **Device Owner (Admin de Dispositivo)** num ambiente MDM corporativo, você precisa de alguns componentes fundamentais do Android SDK (`DevicePolicyManager`, `WorkManager` para o Heartbeat, etc.).

Como um APK Android exige uma estrutura de pastas específica (com `build.gradle`, `AndroidManifest.xml`, etc.), preparei este **esboço completo** com as classes vitais que você precisará criar no Android Studio.

## 1. Configurações Iniciais (`AndroidManifest.xml`)

O Manifesto precisa declarar o "Receiver" do Device Admin e as permissões rigorosas de internet, boot e status do aparelho.

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.elion.mdm.agent">

    <!-- Permissões Básicas -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />
    <uses-permission android:name="android.permission.ACCESS_WIFI_STATE"/>

    <application
        android:allowBackup="false"
        android:icon="@mipmap/ic_launcher"
        android:label="MDM Enterprise Agent"
        android:theme="@style/Theme.ElionMDM">

        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <!-- 🚀 O CORAÇÃO DO DEVICE OWNER -->
        <receiver
            android:name=".receivers.AdminReceiver"
            android:description="@string/app_name"
            android:label="@string/app_name"
            android:permission="android.permission.BIND_DEVICE_ADMIN"
            android:exported="true">
            <meta-data
                android:name="android.app.device_admin"
                android:resource="@xml/device_admin_policies" />
            <intent-filter>
                <action android:name="android.app.action.DEVICE_ADMIN_ENABLED" />
                <action android:name="android.app.action.PROFILE_PROVISIONING_COMPLETE"/>
            </intent-filter>
        </receiver>

    </application>
</manifest>
```

Você também precisará do arquivo `res/xml/device_admin_policies.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<device-admin xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-policies>
        <limit-password />
        <watch-login />
        <reset-password />
        <force-lock />
        <wipe-data />
        <expire-password />
        <encrypted-storage />
        <disable-camera />
    </uses-policies>
</device-admin>
```

---

## 2. O Receiver do Device Admin (`AdminReceiver.kt`)

Esta é a classe que ouve eventos de segurança do sistema Android.

```kotlin
package com.elion.mdm.agent.receivers

import android.app.admin.DeviceAdminReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

class AdminReceiver : DeviceAdminReceiver() {

    override fun onEnabled(context: Context, intent: Intent) {
        super.onEnabled(context, intent)
        Log.d("MDM_AGENT", "Device Admin Habilitado!")
        // Aqui você pode iniciar a sincronização inicial
    }

    override fun onProfileProvisioningComplete(context: Context, intent: Intent) {
        super.onProfileProvisioningComplete(context, intent)
        Log.d("MDM_AGENT", "Provisionamento Corporativo Concluído!")
        
        // Exemplo: Lançar a tela inicial assim que o provisionamento acaba
        val launchIntent = context.packageManager.getLaunchIntentForPackage(context.packageName)
        launchIntent?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(launchIntent)
    }

    override fun onDisabled(context: Context, intent: Intent) {
        super.onDisabled(context, intent)
        Log.d("MDM_AGENT", "Device Admin Desabilitado (Isso não deveria acontecer em Prod!)")
    }
}
```

---

## 3. Gestor de Políticas (`PolicyManager.kt`)

Serviço que aplica as funções restritivas chamando a API nativa do Android.

```kotlin
package com.elion.mdm.agent.managers

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import com.elion.mdm.agent.receivers.AdminReceiver

class PolicyManager(private val context: Context) {

    private val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    private val adminComponent = ComponentName(context, AdminReceiver::class.java)

    // Verifica se realmente somos donos do dispositivo
    fun isDeviceOwner(): Boolean {
        return dpm.isDeviceOwnerApp(context.packageName)
    }

    // Desabilitar Câmera
    fun setCameraDisabled(disabled: Boolean) {
        if (isDeviceOwner()) {
            dpm.setCameraDisabled(adminComponent, disabled)
        }
    }

    // Modo Kiosk (Fixar app na tela e impedir de sair)
    fun setKioskMode(active: Boolean) {
        if (isDeviceOwner()) {
            val packages = if (active) arrayOf(context.packageName) else emptyArray()
            dpm.setLockTaskPackages(adminComponent, packages)
        }
    }

    // Wipe (Cuidado! Formata o aparelho)
    fun wipeDevice() {
        if (isDeviceOwner()) {
            dpm.wipeData(0)
        }
    }
    
    // Obter Serial do aparelho (Necessário Android 10+)
    fun getDeviceSerial(): String {
        return try {
            if (isDeviceOwner()) {
                android.os.Build.getSerial()
            } else {
                "UNKNOWN"
            }
        } catch (e: SecurityException) {
            "PERMISSION_DENIED"
        }
    }
}
```

---

## 4. Comunicação com a API (`ApiService.kt`)

Sugiro usar o **Retrofit** para falar com seu backend FastAPI.

```kotlin
package com.elion.mdm.agent.api

import retrofit2.http.Body
import retrofit2.http.POST
import retrofit2.http.Path

// Modelos de dados baseados no seu design do MDM Enterprise
data class EnrollRequest(
    val serial: String,
    val model: String,
    val android_version: String,
    val enterprise_token: String
)

data class EnrollResponse(
    val device_id: String,
    val auth_token: String,
    val sync_interval: Int
)

data class HeartbeatRequest(
    val battery_level: Int,
    val is_kiosk_active: Boolean
)

data class HeartbeatResponse(
    val commands: List<Command>,
    val policies: PolicyMap
)

interface MdmApiService {
    
    @POST("/api/devices/enroll")
    suspend fun enrollDevice(@Body request: EnrollRequest): EnrollResponse

    @POST("/api/devices/{id}/heartbeat")
    suspend fun sendHeartbeat(
        @Path("id") deviceId: String, 
        @Body info: HeartbeatRequest
    ): HeartbeatResponse
}
```

---

## 5. Worker de Heartbeat (`HeartbeatWorker.kt`)

Usando "WorkManager", para garantir que, de X em X minutos, este código rode em background e se comunique com sua fila de comandos no FastAPI.

```kotlin
package com.elion.mdm.agent.workers

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import com.elion.mdm.agent.managers.PolicyManager

class HeartbeatWorker(
    appContext: Context, 
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): Result {
        val policyManager = PolicyManager(applicationContext)
        
        // Coleta Nível de Bateria
        val batteryStatus: Intent? = IntentFilter(Intent.ACTION_BATTERY_CHANGED).let { ifilter ->
            applicationContext.registerReceiver(null, ifilter)
        }
        val batteryLevel = batteryStatus?.let { intent ->
            val level: Int = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
            val scale: Int = intent.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
            level * 100 / scale
        } ?: -1

        try {
            // OBS: Aqui instanciaríamos o Retrofit/ApiService
            // val api = RetrofitClient.apiService
            // val response = api.sendHeartbeat("device_id_aqui", HeartbeatRequest(batteryLevel, false))
            
            // Aqui lemos os comandos
            // if (response.commands.contains("WIPE")) policyManager.wipeDevice()
            // if (response.policies.camera_disabled) policyManager.setCameraDisabled(true)

            return Result.success()
        } catch (e: Exception) {
            return Result.retry() // Se cair a internet, tenta de novo depois
        }
    }
}
```

---

## 6. A Tela Inicial (`MainActivity.kt`)

Tela simples que o usuário vê (geralmente uma tela de bloqueio com status).

```kotlin
package com.elion.mdm.agent

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.elion.mdm.agent.managers.PolicyManager
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit
import com.elion.mdm.agent.workers.HeartbeatWorker

class MainActivity : AppCompatActivity() {

    private lateinit var policyManager: PolicyManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main) // Crie um layout XML com Textos/Botões de Status

        policyManager = PolicyManager(this)
        
        val statusText = findViewById<TextView>(R.id.text_status)
        val testKioskBtn = findViewById<Button>(R.id.btn_kiosk)

        if (policyManager.isDeviceOwner()) {
            statusText.text = "Status: GERENCIADO PELA EMPRESA ✅"
            iniciarHeartbeat()
        } else {
            statusText.text = "Status: NÃO GERENCIADO ❌\n(Você precisa provisionar via QR Code/ADB)"
        }

        testKioskBtn.setOnClickListener {
            if (policyManager.isDeviceOwner()) {
                // Prende o usuário neste App
                startLockTask() 
                policyManager.setKioskMode(true)
            }
        }
    }

    private fun iniciarHeartbeat() {
        // Envia um Heartbeat a cada 15 minutos (mínimo exigido pelo Android WorkManager)
        val request = PeriodicWorkRequestBuilder<HeartbeatWorker>(15, TimeUnit.MINUTES).build()
        WorkManager.getInstance(this).enqueue(request)
    }
}
```

## Como esse App entrará no celular?

Para ser "Device Owner", o aplicativo **NÃO pode ser baixado da Play Store ou via APK comum e rodado**. Ele precisa ser provisionado num celular "zerado" (Factory Reset).

Existem duas formas pro Dev testar:

**1. ADB (Sem formatar o celular - apenas para emulador ou conta sem Google ligada)**
No terminal com o celular plugado:
```bash
# Instala o app via cabo
adb install SeuApkDoProjeto.apk
# Define como dono do sistema silenciosamente
adb shell dpm set-device-owner com.elion.mdm.agent/.receivers.AdminReceiver
```

**2. Managed Provisioning (QR Code - Oficial do Google para Celulares Novos)**
Na tela de "Bem Vindo / Olá" num celular que acabou de ser formatado, você toca 6 vezes em um lugar em branco na tela. A câmera abrirá para ler um QR code no padrão:
```json
{
    "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME": "com.elion.mdm.agent/.receivers.AdminReceiver",
    "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION": "https://seu-servidor.com/app.apk",
    "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_CHECKSUM": "X...",
    "android.app.extra.PROVISIONING_WIFI_SSID": "SuaRede",
    "android.app.extra.PROVISIONING_WIFI_PASSWORD": "SuaSenha"
}
```
Isso é o que seu MDM Backend ou Admin Panel terá que gerar futuramente.
