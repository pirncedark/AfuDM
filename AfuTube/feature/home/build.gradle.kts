plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
}
android {
    namespace = "com.afudm.afutube.featurehome"
    compileSdk = 34
    defaultConfig { minSdk = 24 }
}
dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
}
