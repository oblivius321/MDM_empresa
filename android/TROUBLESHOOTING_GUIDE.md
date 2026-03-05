# Elion MDM - Troubleshooting & Common Issues

Guia de resolução de problemas comuns encontrados durante desenvolvimento e testes.

---

## 🔧 Issues de Build

### Issue: Gradle Build Falha com Erro "Could not find AGP"
**Erro Completo:**
```
Could not find com.android.tools.build:gradle:8.1.0
```

**Solução:**
1. Verifique internet connection
2. Sincronize Gradle: `./gradlew --refresh-dependencies`
3. Limpe cache: `./gradlew clean`
4. Verifique in AndroidStudio: File → Invalid Caches → Invalidate Caches

---

### Issue: Build Compilation Erro em Kotlin
**Erro Comum:**
```
error: unresolved reference: 'MDMService'
```

**Soluções por Ordem:**
1. Rebuild Project: `./gradlew clean build`
2. Sync com gradle files: `./gradlew cleanBuildCache`
3. Verifique imports: `import com.example.androidmdm.MDMService`
4. Se ainda falhar, reinicie Android Studio

---

### Issue: Proguard/R8 Obfuscation Problemas
**Erro ao Executar APK Release:**
```
Error: type `java.lang.ClassNotFoundException` not resolvable
```

**Solução:**
Edite `proguard-rules.pro`:
```proguard
# Keep MDM classes
-keep class com.example.androidmdm.** { *; }

# Keep API models
-keep class com.example.androidmdm.network.** { *; }

# Keep Retrofit interfaces
-keep interface com.example.androidmdm.network.ElionAPI { *; }

# Keep model classes
-keepclassmembers class * {
    @com.google.gson.annotations.SerializedName <fields>;
}

# Keep enums
-keepclassmembers enum * {
    public static **[] values();
    public static ** valueOf(java.lang.String);
}
```

---

### Issue: Dependency Conflict
**Erro:**
```
Gradle sync failed: Attribute 'version' has different value in two libraries
```

**Solução:**
Edite `gradle/libs.versions.toml`:
```toml
[versions]
kotlin = "1.9.20"  # Use consistente version
compose = "2024.02.02"

[libraries]
kotlin-stdlib = { group = "org.jetbrains.kotlin", name = "kotlin-stdlib", version.ref = "kotlin" }
compose-ui = { group = "androidx.compose.ui", name = "ui", version.ref = "compose" }
```

---

## 📱 Issues de Runtime

### Issue: "Device owner not set" - App não é Device Admin
**Erro no Logcat:**
```
E/ElionMDM: Device owner not set!
E/ElionMDM:DevicePolicyManager (admin) is null
```

**Passos de Resolução:**

1. **Verificar Device Owner:**
```bash
adb shell dpm get-device-owner
# Esperado: com.example.androidmdm/.ElionAdminReceiver
# Se vazio: device owner não está set
```

2. **Reconfigurar Device Owner:**
```bash
# Factory reset necessário se já has outro admin
adb shell dpm set-device-owner com.example.androidmdm/.ElionAdminReceiver

# Verificar após executar
adb shell dpm get-device-owner
```

3. **Se Factory Reset Falhar:**
- Use ADB em recovery mode
- Reboot: `adb reboot recovery`
- Wipe from menu

---

### Issue: MDMService Não Inicia
**Sintomas:**
- MainActivity mostra "Enrollment pending" permanentemente
- WorkManager não roda check-in

**Debug Steps:**

1. **Verificar se Service está rodando:**
```bash
adb shell dumpsys activity services | grep MDMService
# Expected: MDMService visible in output
```

2. **Verificar Logs:**
```bash
adb logcat | grep ElionMDM
# Procure por lines com "startForeground" ou "onCreate"
```

3. **Forçar Start Service:**
```bash
adb shell am startservice com.example.androidmdm/.MDMService
```

4. **Verificar Permissions:**
```bash
adb shell pm grant com.example.androidmdm android.permission.ACCESS_FINE_LOCATION
adb shell pm grant com.example.androidmdm android.permission.SYSTEM_ALERT_WINDOW
adb shell pm grant com.example.androidmdm android.permission.PACKAGE_USAGE_STATS
```

---

### Issue: WorkManager Não Executa Check-in
**Sintomas:**
- Logs mostram "workmanager not triggering"
- Check-ins não acontecem a cada 15 minutos

**Causas & Soluções:**

**Causa 1: Battery Optimization Agressiva**
```bash
# Desabilitar otimização para app
adb shell pm dump com.example.androidmdm | grep BATTERY_MANAGER

# Desabilitar battery optimization (settings manual no device)
Settings → Battery → Battery Saver → No restriction (para app)
```

**Causa 2: WorkManager Constraints Não Atendidas**
```bash
# Verificar se constraints estão OK
adb shell dumpsys jobscheduler | grep androidmdm
```

Se mostrar "constraints_not_satisfied", verificar:
```kotlin
// Em MDMService.kt
val workRequest = PeriodicWorkRequestBuilder<CheckInWorker>(15, TimeUnit.MINUTES)
    .setConstraints(Constraints.Builder()
        .setRequiredNetworkType(NetworkType.CONNECTED)  // Precisa de rede
        .setRequiresBatteryNotLow(false)  // Pode rodar mesmo com bateria baixa
        .build())
    .build()
```

**Causa 3: App Foi Forçado a Parar**
```bash
adb shell cmd appops get com.example.androidmdm SCHEDULE_EXACT_ALARM
# Se não permitido, conceder:
adb shell cmd appops set com.example.androidmdm SCHEDULE_EXACT_ALARM allow
```

---

### Issue: Check-in Falha com "401 Unauthorized"
**Erro em API:**
```
POST /check-in
Response: 401 { "detail": "Invalid or expired token" }
```

**Soluções:**

1. **Verificar Device ID:**
```bash
adb shell am start -n com.example.androidmdm/.MainActivity

# Em logcat, buscar:
D/ElionMDM:MainActivity: Device ID: abc-123-def
```

2. **Backend Deve Reconhecer Device:**
```bash
# No servidor backend
curl -X GET http://localhost:8000/api/devices/abc-123-def \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

3. **Se Device Não Existe:**
```bash
# Enviar primeiro check-in para registrar
adb shell am startservice com.example.androidmdm/.MDMService

# Aguardar 5 segundos e verificar logs
adb logcat | grep "Check-in response"
```

---

### Issue: LocationProvider Retorna Null
**Sintomas:**
- Telemetry enviada com latitude/longitude null
- Logs mostram "Location not available"

**Soluções:**

1. **Garantir Permissão de Location:**
```bash
adb shell pm grant com.example.androidmdm android.permission.ACCESS_FINE_LOCATION
adb shell pm grant com.example.androidmdm android.permission.ACCESS_COARSE_LOCATION
adb shell pm grant com.example.androidmdm android.permission.ACCESS_BACKGROUND_LOCATION
```

2. **Verificar Configurações no Device:**
- Settings → Location → On
- Location Services → High Accuracy (prefira)

3. **Simular Location em Emulator:**
```bash
adb emu geo fix -180 -90  # Coordenadas: -180 longitude, -90 latitude
adb emu geo fix 40.7128 -74.0060  # NYC exemplo
```

4. **Debug Location Request:**
```kotlin
// Em LocationProvider.kt, verificar:
Log.d(TAG, "Current location: ${location?.latitude}, ${location?.longitude}")
// Se nolo, aumentar timeout:
private val locationTimeout = 30_000  // Aumentar de 10 para 30 segundos
```

---

### Issue: Camera Disable/Enable Não Funciona
**Comando Executado Mas Camera Ainda Funciona:**

1. **Verificar Device Owner Status:**
```bash
adb shell dpm get-device-owner
# Deve retornar com.example.androidmdm/.ElionAdminReceiver
```

2. **Verificar Code em PolicyManager:**
```kotlin
fun disableCamera(disabled: Boolean) {
    val restrictions = if (disabled) {
        arrayOf(UserManager.DISALLOW_CAMERA)
    } else {
        emptyArray()
    }
    
    for (restriction in restrictions) {
        if (disabled) {
            devicePolicyManager.addUserRestriction(adminComponent, restriction)
        } else {
            devicePolicyManager.clearUserRestriction(adminComponent, restriction)
        }
    }
}
```

3. **Se Não Funcionar, Usar Policy:**
```kotlin
devicePolicyManager.setCameraDisabled(adminComponent, disabled)
```

---

### Issue: Reboot Command Não Funciona
**Erro:**
```
E/ElionMDM: SecurityException when calling reboot
```

**Solução:**
```kotlin
fun rebootDevice() {
    return try {
        // Método 1: Device Policy Manager (requer Device Owner)
        devicePolicyManager.reboot(adminComponent)
    } catch (e: Exception) {
        Log.e(TAG, "DPM reboot failed, trying alternative", e)
        // Fallback: PowerManager (requer REBOOT permission)
        val pm = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        pm.reboot("Commanded reboot from MDM")
    }
}
```

Verificar manifest:
```xml
<uses-permission android:name="android.permission.REBOOT" />
```

---

### Issue: Wipe Device Não Funciona
**Comando Executado Mas Device Não É Wipado:**

```kotlin
fun wipeDeviceData() {
    // Deve ser executado como Device Owner
    devicePolicyManager.wipeData(
        /* flags */ DevicePolicyManager.WIPE_ALL_DATA or DevicePolicyManager.WIPE_RESET_PROTECTION_DATA
    )
}
```

⚠️ **CUIDADO:** Este comando é irreversível! Teste apenas em emulator.

---

## 🌐 Issues de Network

### Issue: API Timeout - "Read timed out after X seconds"
**Erro:**
```
java.net.SocketTimeoutException: timeout after 30 seconds
```

**Soluções:**

1. **Aumentar Timeout:**
```kotlin
private fun createHttpClient(): OkHttpClient {
    OkHttpClient.Builder()
        .connectTimeout(60, TimeUnit.SECONDS)  // Aumentado de 30
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()
}
```

2. **Verificar Backend Responsivo:**
```bash
curl -v http://YOUR_API/health
# Se lenta, investigar backend performance
```

3. **Aumentar WorkManager Backoff:**
```kotlin
.setBackoffPolicy(BackoffPolicy.EXPONENTIAL, 10, TimeUnit.MINUTES)  // Aumentado
```

---

### Issue: SSL Certificate Error
**Erro:**
```
SSL handshake failed: javax.net.ssl.SSLHandshakeException
```

**Por Ambiente:**

**Development:**
```kotlin
if (BuildConfig.DEBUG) {
    val trustAllCerts = arrayOf<TrustManager>(object : X509TrustManager {
        override fun getAcceptedIssuers(): Array<X509Certificate>? = null
        override fun checkClientTrusted(certs: Array<X509Certificate>, authType: String) {}
        override fun checkServerTrusted(certs: Array<X509Certificate>, authType: String) {}
    })
    
    val sslContext = SSLContext.getInstance("SSL")
    sslContext.init(null, trustAllCerts, SecureRandom())
    builder.sslSocketFactory(sslContext.socketFactory, trustAllCerts[0] as X509TrustManager)
}
```

**Production:**
Implementar certificate pinning (veja Security Checklist).

---

### Issue: Proxy/VPN Interceptando Traffic
**Sintomas:**
- Check-in funciona em casa mas não funciona em corporate network

**Debug:**
```bash
adb shell settings list global | grep -i proxy
# If proxy set, check if app configured for it

# Test with curl from device:
adb shell curl -v http://YOUR_API/check-in
```

**Solução:**
Se necessário suportar proxy:
```kotlin
val proxy = Proxy(Proxy.Type.HTTP, InetSocketAddress("proxy.example.com", 8080))
OkHttpClient.Builder()
    .proxy(proxy)
    .build()
```

---

## 🧪 Issues de Teste

### Issue: Instrumentation Tests Crash
**Erro:**
```
androidx.test.espresso.NoMatchingViewException: No views in hierarchy
```

**Solução:**
```kotlin
// Em setup.ts do teste
@Before
fun setUp() {
    // Aguardar composable renderizar
    composeTestRule.waitUntil(timeoutMillis = 5000) {
        composeTestRule.onRoot().fetchSemanticsNode().isDisplayed
    }
}
```

---

### Issue: Unit Tests Falham com DatabaseException
**Erro:**
```
android.database.sqlite.SQLiteException
```

**Solução:**
Usa SQLite em memória para testes:
```kotlin
@Before
fun setUp() {
    val testDb = Room.inMemoryDatabaseBuilder(
        ApplicationProvider.getApplicationContext(),
        AppDatabase::class.java
    ).build()
}
```

---

## 📊 Issues de Performance

### Issue: App Consome Muita Bateria
**Sintomas:**
- Battery drains 5% por hora com app em background

**Debug:**
```bash
adb shell dumpsys batterystats --reset
# Use app for 1 hour
adb shell dumpsys batterystats | grep BATTERY
```

**Otimizações:**

1. **Aumentar Check-in Interval:**
```kotlin
// De 15 para 30 minutos
PeriodicWorkRequestBuilder<CheckInWorker>(30, TimeUnit.MINUTES)
```

2. **Usar PRIORITY_BALANCED_POWER_ACCURACY:**
```kotlin
// Em LocationProvider.kt
LocationRequest.Builder(Priority.PRIORITY_BALANCED_POWER_ACCURACY, 5000)
```

3. **Limitar Frequency:**
```kotlin
// Executar apenas quando on WiFi
.setConstraints(Constraints.Builder()
    .setRequiredNetworkType(NetworkType.UNMETERED)  // WiFi only
    .build())
```

---

### Issue: App Crash com OutOfMemoryError
**Erro:**
```
java.lang.OutOfMemoryError: Java heap space
```

**Soluções:**

1. **Profile com Android Profiler:**
- AndroidStudio → Profile → Open Profiler
- Monitor Heap Size

2. **Check de Memory Leaks:**
```kotlin
// Em MainActivity.kt
override fun onDestroy() {
    super.onDestroy()
    // Clean references
    _binding = null
}
```

3. **Limitar Cache:**
```kotlin
// Em InventoryManager.kt
private val appCache = LruCache<String, String>(maxSize = 100)
```

---

## 🔄 Issues de Update/Migration

### Issue: App Crash após Update
**Cenário:** User instala versão 1.0.1 trazendo de 1.0.0

**Solução - Feature Flag:**
```kotlin
// CheckInWorker.kt
val version = BuildConfig.VERSION_NAME  // "1.0.1"
val supportsNewFeature = version >= "1.0.1"

if (supportsNewFeature) {
    // nova lógica
} else {
    // fallback
}
```

---

### Issue: Upgrade de Database Schema
**Erro:**
```
android.database.sqlite.SQLiteException: no such column: latitude
```

**Migration Code:**
```kotlin
val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(database: SupportSQLiteDatabase) {
        database.execSQL("ALTER TABLE telemetry ADD COLUMN latitude REAL DEFAULT NULL")
        database.execSQL("ALTER TABLE telemetry ADD COLUMN longitude REAL DEFAULT NULL")
    }
}

Room.databaseBuilder(context, AppDatabase::class.java, "mdm_db")
    .addMigrations(MIGRATION_1_2)
    .build()
```

---

## 📞 Escalação

Se nenhuma solução funcionar:

1. **Coletar Informações:**
```bash
adb logcat -d > logcat_dump.txt
adb bugreport > bug_report.zip
adb getprop > device_properties.txt
```

2. **Abra Issue no GitHub:**
- Título: "MDMService não inicia em Android 12"
- Descrição: Cole logcat_dump.txt
- Device info: paste device_properties.txt

3. **Contacte Time:**
- Slack: #mdm-android-support
- Email: mdm-team@example.com

---

**Frequência de Update:** Semanal durante desenvolvimento  
**Última Atualização:** Março 5, 2026  
**Versão:** 1.0.0
