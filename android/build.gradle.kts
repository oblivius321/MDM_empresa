// Root-level build file — plugins are declared here but NOT applied,
// so the app module can apply them.
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android)      apply false
}
