package com.example.androidmdm.network

import okhttp3.CertificatePinner

/**
 * ✅ SEGURANÇA (FASE 4): Certificate Pinning
 * 
 * Previne Man-in-the-Middle (MITM) attacks ao validar certificado específico
 * do servidor. Mesmo se um atacante conseguir um certificado válido para o domínio,
 * ele não será aceito se não corresponder ao pino (pin).
 * 
 * Como usar:
 * val pinnedCert = CertificatePinning.getPinner()
 * val okHttpClient = OkHttpClient.Builder()
 *      .certificatePinner(pinnedCert)
 *      .build()
 */
object CertificatePinning {
    
    /**
     * Retorna CertificatePinner configurado com certificados da Empresa
     * 
     * IMPORTANTE: Os SHA256 hashes abaixo devem ser atualizados com os certificados reais!
     * 
     * Para obter o SHA256 do certificado do servidor:
     * 1. openssl s_client -connect painel.empresa.com:443 -showcerts < /dev/null
     * 2. openssl x509 -inform PEM -in cert.pem -outform DER | openssl dgst -sha256 -binary | openssl enc -base64
     * 
     * Ou usar: nslookup -type=A painel.empresa.com && certbot show --cert painel.empresa.com
     */
    fun getPinner(): CertificatePinner {
        return CertificatePinner.Builder()
            // ✅ Certificado principal (Let's Encrypt ou CA corporativa)
            .add(
                "painel.empresa.com",
                "sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="  // TODO: Atualizar com SHA256 real
            )
            // ✅ Certificado de backup (para renovação sem downtime)
            .add(
                "painel.empresa.com",
                "sha256/BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB="  // TODO: Atualizar com SHA256 de backup
            )
            // ✅ APIs adicionais (se aplicável)
            .add(
                "api.empresa.com",
                "sha256/CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC="  // TODO: Atualizar
            )
            .build()
    }
    
    /**
     * Gera SHA256 do certificado público
     * 
     * Uso em desenvolvimento:
     * echo | openssl s_client -connect localhost:443 -showcerts | openssl x509 -outform DER | openssl dgst -sha256 -binary | openssl enc -base64
     */
    fun generateSHA256(domain: String, port: Int = 443): String {
        // Em produção, usar Process para executar openssl (não recomendado em app)
        // Para testes, usar ferramentas externas e copiar resultado
        return "GERAR_COM_OPENSSL"
    }
}

/**
 * ✅ SEGURANÇA: Configuração por Ambiente
 * 
 * Desenvolvimento (localhost):
 * - Certificate pinning DESATIVADO (usa self-signed)
 * - Base URL: https://10.0.2.2:443/api/ (com ignore self-signed)
 * 
 * Staging (teste.empresa.com):
 * - Certificate pinning ATIVADO
 * - Base URL: https://teste.empresa.com/api/
 * 
 * Produção (painel.empresa.com):
 * - Certificate pinning ATIVADO
 * - Base URL: https://painel.empresa.com/api/
 */
object EnvironmentConfig {
    
    enum class Environment {
        DEVELOPMENT,
        STAGING,
        PRODUCTION
    }
    
    // TODO: Ler de BuildConfig.FLAVOR ou similar
    val currentEnvironment = Environment.PRODUCTION
    
    val apiBaseUrl: String
        get() = when (currentEnvironment) {
            Environment.DEVELOPMENT -> "https://10.0.2.2:443/api/"
            Environment.STAGING -> "https://teste.empresa.com/api/"
            Environment.PRODUCTION -> "https://painel.empresa.com/api/"
        }
    
    val shouldPinCertificates: Boolean
        get() = currentEnvironment != Environment.DEVELOPMENT
}
