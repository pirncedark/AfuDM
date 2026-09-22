plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp") version "2.4.10-2.0.2"
}

android {
    namespace = "com.afudm.afutube"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.afudm.afutube"
        minSdk = 24
        targetSdk = 37
        versionCode = 1
        versionName = "1.0.0"

        // ABI split — arm64-v8a öncelikli, diğerleri ayrı APK
        ndk {
            abiFilters.add("arm64-v8a")
            abiFilters.add("armeabi-v7a")
        }
    }

    // ABI-bazlı APK split (boyut için)
    splits {
        abi {
            isEnable = true
            reset()
            include("arm64-v8a", "armeabi-v7a", "x86", "x86_64")
            isUniversalApk = true   // universal APK da üret
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

dependencies {
    // ── Compose BOM ──────────────────────────────────────────────────────────
    val composeBom = platform("androidx.compose:compose-bom:2026.09.00")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    // ── AndroidX core ────────────────────────────────────────────────────────
    implementation("androidx.core:core-ktx:1.19.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
    implementation("androidx.activity:activity-compose:1.8.2")
    implementation("androidx.navigation:navigation-compose:2.10.1")

    // ── WorkManager (uzun indirmeler için) ───────────────────────────────────
    implementation("androidx.work:work-runtime-ktx:2.9.0")

    // ── Room (indirme geçmişi DB) ─────────────────────────────────────────
    val roomVersion = "2.8.5"
    implementation("androidx.room:room-runtime:$roomVersion")
    implementation("androidx.room:room-ktx:$roomVersion")
    ksp("androidx.room:room-compiler:$roomVersion")

    // ── youtubedl-android (yt-dlp + FFmpeg + aria2 wrapper) ─────────────────
    // Resmi repo: https://github.com/yausername/youtubedl-android
    implementation("com.github.yausername.youtubedl-android:library:0.14.0")
    implementation("com.github.yausername.youtubedl-android:ffmpeg:0.14.0")
    implementation("com.github.yausername.youtubedl-android:aria2c:0.14.0")


    // ── Coil (thumbnail yükleme) ──────────────────────────────────────────
    implementation("io.coil-kt:coil-compose:2.5.0")

    // ── Coroutines ───────────────────────────────────────────────────────────
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // ── DataStore (ayarlar) ───────────────────────────────────────────────
    implementation("androidx.datastore:datastore-preferences:1.0.0")

    // ── Proje modülleri ───────────────────────────────────────────────────
    implementation(project(":core"))
    implementation(project(":extractor"))
    implementation(project(":downloader"))
    implementation(project(":media"))
    implementation(project(":updater"))
    implementation(project(":feature:home"))
    implementation(project(":feature:formats"))
    implementation(project(":feature:downloads"))
    implementation(project(":feature:history"))
    implementation(project(":feature:settings"))
    implementation(project(":feature:torrent"))
}
