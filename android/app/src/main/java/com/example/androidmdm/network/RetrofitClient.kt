package com.example.androidmdm.network

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object RetrofitClient {
    // Para Emuladores consumirem o localhost da máquina hospedeira, usa-se 10.0.2.2.
    // Para devices físicos na mesma rede Wi-Fi, seria o IP local do seu PC (ex: 192.168.1.XX).
    private const val BASE_URL = "http://10.0.2.2:8000/api/"

    val api: ElionAPI by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ElionAPI::class.java)
    }
    
    fun getBaseUrl(): String {
        return BASE_URL.replace("/api/", "/")
    }
}
