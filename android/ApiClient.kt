package com.elion.mdm.data.remote

import android.content.Context
import com.elion.mdm.BuildConfig
import com.elion.mdm.data.local.SecurePreferences
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Response
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

/**
 * ApiClient — singleton que constrói e mantém a instância do Retrofit.
 *
 * Cadeia de interceptors OkHttp:
 *   1. AuthInterceptor        → injeta "Authorization: Bearer <token>" e "X-Device-ID"
 *   2. HttpLoggingInterceptor → loga request/response apenas em builds DEBUG
 *
 * A URL base vem das SecurePreferences, permitindo configuração dinâmica
 * via tela de enrollment sem necessidade de recompilar o APK.
 */
object ApiClient {

    private var retrofit: Retrofit? = null
    private var currentBaseUrl: String = ""

    fun getInstance(context: Context): ApiService {
        val prefs   = SecurePreferences(context)
        val baseUrl = normalizeUrl(prefs.backendUrl)

        if (retrofit == null || currentBaseUrl != baseUrl) {
            retrofit       = buildRetrofit(context, baseUrl)
            currentBaseUrl = baseUrl
        }
        return retrofit!!.create(ApiService::class.java)
    }

    fun invalidate() {
        retrofit       = null
        currentBaseUrl = ""
    }

    // ─── Builders ─────────────────────────────────────────────────────────────

    private fun buildRetrofit(context: Context, baseUrl: String) = Retrofit.Builder()
        .baseUrl(baseUrl)
        .client(buildOkHttp(context))
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    private fun buildOkHttp(context: Context): OkHttpClient {
        val logging = HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG)
                HttpLoggingInterceptor.Level.BODY
            else
                HttpLoggingInterceptor.Level.NONE
        }

        return OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(context))
            .addInterceptor(logging)
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30,  TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()
    }

    // ─── Auth Interceptor ─────────────────────────────────────────────────────

    private class AuthInterceptor(private val context: Context) : Interceptor {
        override fun intercept(chain: Interceptor.Chain): Response {
            val prefs = SecurePreferences(context)
            val req   = chain.request().newBuilder().apply {
                addHeader("Content-Type", "application/json")
                prefs.deviceToken?.takeIf { it.isNotBlank() }?.let {
                    addHeader("Authorization", "Bearer $it")
                }
                prefs.deviceId?.takeIf { it.isNotBlank() }?.let {
                    addHeader("X-Device-ID", it)
                }
            }.build()
            return chain.proceed(req)
        }
    }

    // ─── Util ─────────────────────────────────────────────────────────────────

    private fun normalizeUrl(url: String) = if (url.endsWith("/")) url else "$url/"
}
