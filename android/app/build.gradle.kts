import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

val localProperties = Properties()
val localPropertiesFile = rootProject.file("local.properties")
if (localPropertiesFile.exists()) {
    localPropertiesFile.inputStream().use(localProperties::load)
}

fun signingProperty(name: String): String? =
    providers.gradleProperty(name).orNull
        ?: providers.environmentVariable(name).orNull
        ?: localProperties.getProperty(name)

val releaseStoreFile = signingProperty("ELION_RELEASE_STORE_FILE")
val releaseStorePassword = signingProperty("ELION_RELEASE_STORE_PASSWORD")
val releaseKeyAlias = signingProperty("ELION_RELEASE_KEY_ALIAS")
val releaseKeyPassword = signingProperty("ELION_RELEASE_KEY_PASSWORD")
val hasReleaseSigningConfig =
    !releaseStoreFile.isNullOrBlank() &&
        !releaseStorePassword.isNullOrBlank() &&
        !releaseKeyAlias.isNullOrBlank() &&
        !releaseKeyPassword.isNullOrBlank() &&
        rootProject.file(releaseStoreFile!!).isFile

android {
    namespace         = "com.elion.mdm"
    compileSdk        = 35

    defaultConfig {
        applicationId = "com.elion.mdm"
        minSdk        = 30          // Android 11 — requisito mínimo para MDM enterprise moderno
        targetSdk     = 35
        versionCode   = 1
        versionName   = "1.0.0"
    }

    signingConfigs {
        if (hasReleaseSigningConfig) {
            create("release") {
                storeFile = rootProject.file(releaseStoreFile!!)
                storePassword = releaseStorePassword!!
                keyAlias = releaseKeyAlias!!
                keyPassword = releaseKeyPassword!!
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled   = true
            isShrinkResources = true
            if (hasReleaseSigningConfig) {
                signingConfig = signingConfigs.getByName("release")
            }
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            buildConfigField("Boolean", "DEBUG", "false")
        }
        debug {
            isMinifyEnabled = false
            buildConfigField("Boolean", "DEBUG", "true")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        buildConfig = true
        viewBinding = true
    }
}

dependencies {
    // ─── Android Core ─────────────────────────────────────────────────────
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.material)
    implementation(libs.androidx.activity)
    implementation(libs.androidx.constraintlayout)

    // ─── Lifecycle + ViewModel ────────────────────────────────────────────
    implementation(libs.androidx.lifecycle.viewmodel.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)

    // ─── Coroutines ───────────────────────────────────────────────────────
    implementation(libs.kotlinx.coroutines.android)

    // ─── WorkManager ──────────────────────────────────────────────────────
    implementation(libs.androidx.work.runtime.ktx)

    // ─── Security (EncryptedSharedPreferences) ────────────────────────────
    implementation(libs.androidx.security.crypto)

    // ─── Networking ───────────────────────────────────────────────────────
    implementation(libs.retrofit)
    implementation(libs.retrofit.converter.gson)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging.interceptor)

    // ─── Testes ───────────────────────────────────────────────────────────
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
}
