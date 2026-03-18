# ─── Retrofit ────────────────────────────────────────────────────────────────
-keepattributes Signature
-keepattributes Exceptions
-keep class retrofit2.** { *; }
-keepclasseswithmembers class * {
    @retrofit2.http.* <methods>;
}

# ─── Gson / DTOs ──────────────────────────────────────────────────────────────
-keepattributes *Annotation*
-keep class com.google.gson.** { *; }
-keep class com.elion.mdm.data.remote.dto.** { *; }

# ─── OkHttp ───────────────────────────────────────────────────────────────────
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }

# ─── Coroutines ───────────────────────────────────────────────────────────────
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}

# ─── Security Crypto ──────────────────────────────────────────────────────────
-keep class androidx.security.crypto.** { *; }

# ─── Device Admin ─────────────────────────────────────────────────────────────
-keep class com.elion.mdm.AdminReceiver { *; }
-keep class com.elion.mdm.BootReceiver  { *; }
