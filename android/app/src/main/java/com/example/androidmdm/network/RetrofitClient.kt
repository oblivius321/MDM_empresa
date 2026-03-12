package com.example.androidmdm.network

import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManagerFactory

object RetrofitClient {
    
    // ✅ SEGURANÇA (FASE 4): 
    // - HTTPS obrigatório (não HTTP)
    // - Em produção: https://painel.empresa.com/api/
    // - Em teste local: https://10.0.2.2:443/api/ (com self-signed cert)
    private const val BASE_URL = "https://painel.empresa.com/api/"
    
    // Armazena o token de acesso de maneira estática após inicialização
    private var accessToken: String = ""

    fun init(context: android.content.Context) {
        val prefs = context.getSharedPreferences("ElionMDMPrefs", android.content.Context.MODE_PRIVATE)
        accessToken = prefs.getString("DEVICE_TOKEN", "") ?: ""
    }
    
    // ✅ SEGURANÇA: OkHttpClient configurado com TLS 1.2+
    private val okHttpClient: OkHttpClient by lazy {
        val trustManager = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm())
        trustManager.init(null as? java.security.KeyStore?)
        
        val sslContext = SSLContext.getInstance("TLSv1.2").apply {
            init(null, trustManager.trustManagers, java.security.SecureRandom())
        }
        
        OkHttpClient.Builder()
            // ✅ TLS 1.2+ obrigatório (sem SSL 3.0, TLS 1.0, 1.1)
            .sslSocketFactory(sslContext.socketFactory, trustManager.trustManagers[0] as javax.net.ssl.X509TrustManager)
            // ✅ Adicionar security headers ao interceptor
            .addInterceptor { chain ->
                val originalRequest = chain.request()
                val newRequest = originalRequest.newBuilder()
                    .header("Cache-Control", "no-cache, no-store, must-revalidate")
                    .header("Pragma", "no-cache")
                    .header("X-Requested-With", "com.example.androidmdm")
                    // ✅ Adicionar Header de Device Token Seguro
                    .header("x-device-token", accessToken)
                    .build()
                
                // ✅ Validar que é HTTPS (não permitir HTTP em produção)
                if (!newRequest.url.scheme.equals("https", ignoreCase = true)) {
                    throw IllegalArgumentException("❌ HTTPS obrigatório. URL: ${newRequest.url}")
                }
                
                chain.proceed(newRequest)
            }
            // ✅ Timeout de segurança
            .connectTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
            .readTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
            .writeTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
            .build()
    }

    val api: ElionAPI by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ElionAPI::class.java)
    }
    
    fun getBaseUrl(): String {
        return BASE_URL.replace("/api/", "/")
    }
}
