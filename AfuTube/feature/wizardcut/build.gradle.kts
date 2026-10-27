import groovy.json.JsonSlurper
import java.security.MessageDigest
import java.util.Locale
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

// WizardCut (MIT, SysAdminDoc + BigWizard Media) — https://github.com/BigWizard94/wizardcut v3.81.0
// Uygulama modülü kütüphaneye çevrildi; kod aynen, paket adı info.bigwizardmedia.wizardcut korunur.
plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.dagger.hilt.android")
    id("com.google.devtools.ksp")
}

val runtimeNoticeGeneratedDir = layout.buildDirectory.dir("generated/source/runtimeNotices")

android {
    namespace = "info.bigwizardmedia.wizardcut"
    compileSdk = 37

    defaultConfig {
        minSdk = 26
        consumerProguardFiles("proguard-rules.pro")
        buildConfigField("String", "APPLICATION_ID", "\"info.bigwizardmedia.wizardcut\"")
        buildConfigField("int", "VERSION_CODE", "299")
        buildConfigField("String", "VERSION_NAME", "\"3.81.0\"")
        // AfuTube kendi güncelleyicisini kullanır; WizardCut GitHub sürüm kontrolü kapalı.
        buildConfigField("boolean", "UPDATE_CHECK_AVAILABLE", "false")
        buildConfigField("boolean", "LOCAL_NETWORK_STREAMING_ENABLED", "false")
        buildConfigField("boolean", "QA_TIMELINE_HARNESS_ENABLED", "false")
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    sourceSets {
        getByName("main").java.directories.add(runtimeNoticeGeneratedDir.get().asFile.absolutePath)
    }
}

ksp {
    arg("room.schemaLocation", "$projectDir/schemas")
}

val ffmpegKitAar = file("third_party/ffmpeg-kit-next/ffmpeg-kit-next-8.1.0.aar")
val ffmpegKitAarSha256 = "7971240aff84ce59a4ab28400bb4af59d24c20ce68c25525d41d910246ccff62"

fun File.sha256(): String {
    val digest = MessageDigest.getInstance("SHA-256")
    inputStream().buffered().use { input ->
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        while (true) {
            val read = input.read(buffer)
            if (read < 0) break
            digest.update(buffer, 0, read)
        }
    }
    return digest.digest().joinToString("") { "%02x".format(it) }
}

val verifyFfmpegKitAar by tasks.registering {
    group = "verification"
    description = "Verifies the source-pinned FFmpegKitNext AAR before compilation."
    inputs.file(ffmpegKitAar)
    doLast {
        require(ffmpegKitAar.isFile) { "Missing vendored FFmpegKitNext AAR: $ffmpegKitAar" }
        val actual = ffmpegKitAar.sha256()
        require(actual == ffmpegKitAarSha256) {
            "FFmpegKitNext AAR checksum mismatch: expected=$ffmpegKitAarSha256 actual=$actual"
        }
    }
}

// WizardCut'ın kendi lisans listesi (Ayarlar > Açık kaynak) için üretilen sınıf.
// Kaynak: wizardcut app/build.gradle.kts generateRuntimeOpenSourceNotices (sadeleştirilmiş).
data class RuntimeLicenseInfo(val licenseName: String, val licenseText: String, val licenseUrl: String, val projectUrl: String)

val apacheLicense = RuntimeLicenseInfo("Apache License 2.0", "Apache License 2.0. Redistribution must preserve the license and required notices; the software is provided without warranties under the Apache terms.", "https://www.apache.org/licenses/LICENSE-2.0.txt", "https://www.apache.org/")
val mitLicense = RuntimeLicenseInfo("MIT License", "MIT License. Redistribution must keep the copyright and permission notices; the software is provided without warranties.", "https://opensource.org/license/mit/", "https://opensource.org/license/mit/")
val bsd2License = RuntimeLicenseInfo("BSD 2-Clause License", "BSD 2-Clause License. Redistribution must preserve the copyright notice, conditions, and disclaimer.", "https://opensource.org/license/bsd-2-clause/", "https://opensource.org/license/bsd-2-clause/")
val bsd3License = RuntimeLicenseInfo("BSD 3-Clause License", "BSD 3-Clause License. Redistribution must preserve the copyright notice, conditions, and disclaimer.", "https://opensource.org/license/bsd-3-clause/", "https://opensource.org/license/bsd-3-clause/")
val iscLicense = RuntimeLicenseInfo("ISC License", "ISC License. Permission to use, copy, modify, and distribute is granted subject to the included copyright and disclaimer.", "https://opensource.org/license/isc-license-txt/", "https://opensource.org/license/isc-license-txt/")
val lgpl3License = RuntimeLicenseInfo("GNU Lesser General Public License Version 3", "GNU LGPL v3. Redistribution must preserve the license and corresponding notices.", "https://www.gnu.org/licenses/lgpl-3.0.txt", "https://www.gnu.org/licenses/lgpl-3.0.html")
val lgpl21License = RuntimeLicenseInfo("GNU Lesser General Public License Version 2.1 or later", "GNU LGPL v2.1 or later. Redistribution must preserve the license and corresponding notices.", "https://www.gnu.org/licenses/old-licenses/lgpl-2.1.txt", "https://www.gnu.org/licenses/lgpl-2.1.html")
val freetypeLicense = RuntimeLicenseInfo("FreeType License", "FreeType License. Redistribution must preserve the license and its notices.", "https://freetype.org/license.html", "https://freetype.org/")
val libpngLicense = RuntimeLicenseInfo("libpng License", "libpng License. Redistribution must preserve the copyright notice and disclaimer.", "http://www.libpng.org/pub/png/src/libpng-LICENSE.txt", "http://www.libpng.org/pub/png/libpng.html")
val llvmExceptionLicense = RuntimeLicenseInfo("Apache License 2.0 with LLVM exception", "Apache License 2.0 with the LLVM exception. Redistribution must preserve the license and exception text.", "https://llvm.org/LICENSE.txt", "https://llvm.org/")

fun RuntimeLicenseInfo.forProject(url: String) = copy(projectUrl = url)

val runtimeLicensePolicies: List<Pair<String, RuntimeLicenseInfo>> = listOf(
    "com.google.protobuf" to bsd3License,
    "com.google.code.findbugs" to bsd3License,
    "com.microsoft.onnxruntime" to mitLicense.forProject("https://onnxruntime.ai/"),
    "org.checkerframework" to mitLicense.forProject("https://checkerframework.org/"),
    "androidx" to apacheLicense.forProject("https://developer.android.com/jetpack"),
    "org.jetbrains.androidx" to apacheLicense.forProject("https://github.com/JetBrains"),
    "org.jetbrains.compose" to apacheLicense.forProject("https://github.com/JetBrains/compose-multiplatform"),
    "org.jetbrains.kotlinx" to apacheLicense.forProject("https://github.com/Kotlin"),
    "org.jetbrains.kotlin" to apacheLicense.forProject("https://kotlinlang.org/"),
    "org.jetbrains" to apacheLicense.forProject("https://github.com/JetBrains"),
    "com.airbnb.android" to apacheLicense.forProject("https://github.com/airbnb/lottie-android"),
    "com.arthenica" to apacheLicense.forProject("https://github.com/arthenica/ffmpeg-kit"),
    "com.google.dagger" to apacheLicense.forProject("https://dagger.dev/"),
    "com.google.mediapipe" to apacheLicense.forProject("https://mediapipe.dev/"),
    "com.google.firebase" to apacheLicense.forProject("https://firebase.google.com/"),
    "com.google.android.datatransport" to apacheLicense.forProject("https://github.com/firebase/firebase-android-sdk"),
    "com.google.flogger" to apacheLicense.forProject("https://google.github.io/flogger/"),
    "com.google.guava" to apacheLicense.forProject("https://github.com/google/guava"),
    "com.google.j2objc" to apacheLicense.forProject("https://github.com/google/j2objc"),
    "com.google.errorprone" to apacheLicense.forProject("https://errorprone.info/"),
    "com.google" to apacheLicense.forProject("https://developers.google.com/"),
    "com.squareup.okhttp3" to apacheLicense.forProject("https://square.github.io/okhttp/"),
    "com.squareup.okio" to apacheLicense.forProject("https://square.github.io/okio/"),
    "io.coil-kt.coil3" to apacheLicense.forProject("https://github.com/coil-kt/coil"),
    "io.github.kaleyravideo" to apacheLicense.forProject("https://github.com/KaleyraVideo/AndroidDeepFilterNet"),
    "jakarta.inject" to apacheLicense.forProject("https://github.com/jakartaee/inject"),
    "javax.inject" to apacheLicense.forProject("https://github.com/javax-inject/javax-inject"),
    "org.jspecify" to apacheLicense.forProject("https://jspecify.dev/"),
)

fun runtimeLicenseFor(group: String): RuntimeLicenseInfo? = runtimeLicensePolicies
    .filter { (prefix, _) -> group == prefix || group.startsWith("$prefix.") }
    .maxByOrNull { (prefix, _) -> prefix.length }
    ?.second

fun nativeLicenseFor(expression: String): RuntimeLicenseInfo = when (expression) {
    "Apache-2.0" -> apacheLicense
    "Apache-2.0-with-LLVM-exception" -> llvmExceptionLicense
    "BSD-2-Clause" -> bsd2License
    "BSD-3-Clause" -> bsd3License
    "FTL" -> freetypeLicense
    "ISC" -> iscLicense
    "LGPL-2.1-or-later" -> lgpl21License
    "LGPL-3.0-or-later" -> lgpl3License
    "Libpng" -> libpngLicense
    "MIT" -> mitLicense
    else -> error("No native notice license mapping for $expression")
}

fun String.kotlinLiteral(): String = buildString {
    append('"')
    for (c in this@kotlinLiteral) {
        when (c) {
            '\\' -> append("\\\\")
            '"' -> append("\\\"")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            '\t' -> append("\\t")
            '$' -> append("\\$")
            else -> append(c)
        }
    }
    append('"')
}

fun nativeProjectUrl(purl: String): String {
    val githubPath = purl.removePrefix("pkg:github/").substringBefore('@')
    return if (githubPath != purl && githubPath.contains('/')) "https://github.com/$githubPath"
    else if (purl.contains("ffmpeg")) "https://ffmpeg.org/"
    else "https://developer.android.com/ndk"
}

val generateRuntimeOpenSourceNotices by tasks.registering {
    group = "verification"
    description = "Generates the resolved-runtime open-source notice inventory used by WizardCut settings."
    val nativeLockFile = file("third_party/ffmpeg-kit-next/native-lock.json")
    val generatedFile = runtimeNoticeGeneratedDir.map { it.file("RuntimeOpenSourceLicensesGenerated.kt") }
    inputs.file(nativeLockFile)
    inputs.file(project.buildFile)
    outputs.dir(runtimeNoticeGeneratedDir)
    doLast {
        val resolved = configurations.getByName("releaseRuntimeClasspath")
            .incoming.resolutionResult.allComponents
            .mapNotNull { it.moduleVersion }
            .filter { it.version.isNotBlank() && it.group.isNotBlank() }
            .distinctBy { "${it.group}:${it.name}:${it.version}" }
            .sortedWith(compareBy({ it.group }, { it.name }, { it.version }))
        val entries = mutableListOf<Triple<String, String, Pair<String, RuntimeLicenseInfo>>>()
        resolved.forEach { m ->
            val license = runtimeLicenseFor(m.group) ?: return@forEach
            val coordinate = "${m.group}:${m.name}"
            entries += Triple(coordinate, m.version, coordinate to license)
        }
        val nativeLock = JsonSlurper().parse(nativeLockFile) as Map<*, *>
        val nativeEntries = (nativeLock["components"] as List<*>).map { raw ->
            val c = raw as Map<*, *>
            val name = c["name"] as String
            val artifact = "native:" + name.lowercase(Locale.ROOT).replace(Regex("[^a-z0-9]+"), "-").trim('-')
            Triple(name, c["version"] as String, artifact to nativeLicenseFor(c["license"] as String).forProject(nativeProjectUrl(c["purl"] as String)))
        }
        val text = buildString {
            appendLine("package info.bigwizardmedia.wizardcut.engine")
            appendLine()
            appendLine("// Generated by the releaseRuntimeClasspath and native-lock notice task; do not edit.")
            appendLine("internal object RuntimeOpenSourceLicensesGenerated {")
            appendLine("    val notices: List<OpenSourceLicenseNotice> = listOf(")
            (entries.map { it to false } + nativeEntries.map { it to true }).sortedBy { it.first.third.first }.forEach { (e, native) ->
                val (name, version, art) = e
                val (artifact, l) = art
                appendLine("        OpenSourceLicenseNotice(")
                appendLine("            name = ${name.kotlinLiteral()},")
                appendLine("            version = ${version.kotlinLiteral()},")
                appendLine("            artifact = ${artifact.kotlinLiteral()},")
                appendLine("            licenseName = ${l.licenseName.kotlinLiteral()},")
                appendLine("            licenseText = ${l.licenseText.kotlinLiteral()},")
                appendLine("            licenseUrl = ${l.licenseUrl.kotlinLiteral()},")
                appendLine("            projectUrl = ${l.projectUrl.kotlinLiteral()},")
                appendLine("            sourceOfferText = null,")
                appendLine("            complianceNote = ${if (native) "Vendored native component recorded in third_party/ffmpeg-kit-next/native-lock.json.".kotlinLiteral() else "null"},")
                appendLine("        ),")
            }
            appendLine("    )")
            appendLine("}")
        }
        val out = generatedFile.get().asFile
        out.parentFile.mkdirs()
        out.writeText(text)
    }
}

tasks.named("preBuild").configure {
    dependsOn(verifyFfmpegKitAar)
    dependsOn(generateRuntimeOpenSourceNotices)
}
tasks.withType<KotlinCompile>().configureEach {
    dependsOn(generateRuntimeOpenSourceNotices)
    if (!name.contains("UnitTest") && !name.contains("AndroidTest")) source(runtimeNoticeGeneratedDir.get().asFile)
}
tasks.configureEach { if (name.startsWith("ksp") && name.contains("Kotlin")) dependsOn(generateRuntimeOpenSourceNotices) }

dependencies {
    implementation(project(":core")) // AfuColors (tema)
    constraints {
        implementation("com.google.protobuf:protobuf-javalite:4.27.5") {
            because("GHSA-735f-pc8j-v9w8: protobuf-javalite < 4.27.5 is vulnerable to a malformed-input DoS")
        }
    }
    implementation(platform("org.jetbrains.kotlinx:kotlinx-serialization-bom:1.8.1"))

    implementation("androidx.core:core-ktx:1.19.0")
    implementation("androidx.exifinterface:exifinterface:1.3.7")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.window:window:1.5.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.11.0")

    implementation(platform("androidx.compose:compose-bom:2026.09.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.10.0")
    implementation("androidx.navigation:navigation-compose:2.9.8")

    implementation("com.google.dagger:hilt-android:2.60.1")
    ksp("com.google.dagger:hilt-compiler:2.60.1")
    implementation("androidx.hilt:hilt-navigation-compose:1.3.0")

    implementation("androidx.media3:media3-exoplayer:1.11.1")
    implementation("androidx.media3:media3-transformer:1.11.1")
    implementation("androidx.media3:media3-effect:1.11.1")
    implementation("androidx.media3:media3-effect-lottie:1.11.1")
    implementation("androidx.media3:media3-common:1.11.1")
    implementation("androidx.media3:media3-ui:1.11.1")
    implementation("androidx.media3:media3-muxer:1.11.1")

    implementation("androidx.room3:room3-runtime:3.0.1")
    implementation("androidx.sqlite:sqlite-framework:2.7.0")
    ksp("androidx.room3:room3-compiler:3.0.1")

    implementation("androidx.datastore:datastore-preferences:1.2.1")

    implementation("androidx.work:work-runtime-ktx:2.11.2")
    implementation("androidx.hilt:hilt-work:1.3.0")
    ksp("androidx.hilt:hilt-compiler:1.3.0")
    implementation("androidx.profileinstaller:profileinstaller:1.4.1")

    implementation("io.coil-kt.coil3:coil-compose:3.5.0")
    implementation("io.coil-kt.coil3:coil-video:3.5.0")

    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.26.0")
    implementation("com.google.mediapipe:tasks-vision:1.0.0")
    implementation("com.airbnb.android:lottie-compose:6.7.1")

    // Source-pinned LGPL build: FFmpegKitNext 8.1.0 / FFmpeg 8.1.2 (kaynak teklifi res/raw içinde).
    // Yerel AAR kütüphane AAR'ına gömülemez (AGP); burada derleme için, APK'ya :app ekler.
    compileOnly(files(ffmpegKitAar))
    implementation("com.arthenica:smart-exception-java:0.2.1")

    implementation("io.github.kaleyravideo:android-deepfilternet:0.0.8")
    implementation("com.squareup.okhttp3:okhttp:5.5.0")
}
