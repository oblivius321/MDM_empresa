# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# If your project uses WebView with JS, uncomment the following
# and specify the fully qualified class name to the JavaScript interface
# class:
#-keepclassmembers class fqcn.of.javascript.interface.for.webview {
#   public *;
#}

# Uncomment this to preserve the line number information for
# debugging stack traces.
#-keepattributes SourceFile,LineNumberTable

# If you keep the line number information, uncomment this to
# hide the original source file name.
#-renamesourcefileattribute SourceFile

# ✅ SEGURANÇA (FASE 4): ProGuard Rules para Proteção & Funcionalidade

# === Retrofit & OkHttp (Não ofuscar classes de network) ===
# Manter Retrofit annotations intactas
-keep class retrofit2.** { *; }
-keep interface retrofit2.** { *; }
-keepattributes Signature, InnerClasses, EnclosingMethod
-keep class * extends retrofit2.Converter { *; }
-keep class * extends retrofit2.Call { *; }

# OkHttp
-keep class okhttp3.** { *; }
-keep interface okhttp3.** { *; }
-keepclasseswithmembernames class okhttp3.** { *; }

# Gson (para serialização JSON)
-keep class com.google.gson.** { *; }
-keepattributes Signature
-keep class * extends com.google.gson.TypeAdapter
-keep class * implements com.google.gson.TypeAdapterFactory
-keep class * implements com.google.gson.JsonSerializer
-keep class * implements com.google.gson.JsonDeserializer
-keepclassmembers class * {
    !static !transient <fields>;
}
-keep class **.R
-keep class **.R$*

# === Modelos de Dados (Data Classes) ===
# IMPORTANTE: Não ofuscar as data classes (precisam dos nomes originais para JSON mapping)
-keep class com.example.androidmdm.models.** { *; }
-keep class com.example.androidmdm.network.** { 
    public <methods>; 
    public <fields>;
}
-keepclassmembers class com.example.androidmdm.models.** { *; }

# === API Interface (ElionAPI) ===
-keep interface com.example.androidmdm.network.ElionAPI { *; }
-keep class com.example.androidmdm.network.ElionAPI$* { *; }

# === Security Classes (Não ofuscar) ===
-keep class com.example.androidmdm.network.RetrofitClient { *; }
-keep class com.example.androidmdm.network.CertificatePinning { *; }
-keep class com.example.androidmdm.network.EnvironmentConfig { *; }

# === Kotlin Coroutines ===
-keepclassmembernames class kotlinx.coroutines.** { *; }
-keepclasseswithmembers class kotlinx.** {
    *** *(...);
}

# === AndroidX & Google Play Services ===
-keep class androidx.** { *; }
-keep class com.google.android.** { *; }
-keep class com.google.common.** { *; }

# === Android Manifest Components (não ofuscar nomes) ===
-keep public class * extends android.app.Activity
-keep public class * extends android.app.Service
-keep public class * extends android.content.BroadcastReceiver
-keep public class * extends android.content.ContentProvider

# === Remover logging em produção (opcional) ===
-assumenosideeffects class android.util.Log {
    public static *** d(...);
    public static *** v(...);
    public static *** i(...);
}

# === Remove warnings ===
-dontwarn com.squareup.retrofit2.**
-dontwarn okhttp3.**
-dontwarn com.google.gson.**
-dontwarn org.jetbrains.annotations.**
