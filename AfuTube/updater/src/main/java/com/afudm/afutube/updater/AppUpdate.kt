package com.afudm.afutube.updater

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import org.json.JSONArray
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

data class AppUpdate(
    val versionName: String,
    val versionCode: Int,
    val releaseNotes: String,
    val apkUrl: String,
    val checksumUrl: String,
    val minSdk: Int = 24,
    val sha256: String = "",
    val prerelease: Boolean = false
)

object AppVersion {
    fun code(versionName: String): Int = versionName.split('.').let {
        it.getOrNull(0).orEmpty().toIntOrNull().orZero() * 1_000_000 +
            it.getOrNull(1).orEmpty().toIntOrNull().orZero() * 1_000 +
            it.getOrNull(2).orEmpty().substringBefore('-').toIntOrNull().orZero()
    }

    private fun Int?.orZero() = this ?: 0
}

object AppUpdateParser {
    fun latest(json: String, currentVersionCode: Int, includePrereleases: Boolean = false): AppUpdate? {
        val releases = JSONArray(json)
        val candidates = (0 until releases.length()).mapNotNull { index ->
            val release = releases.optJSONObject(index) ?: return@mapNotNull null
            val tag = release.optString("tag_name")
            val prerelease = release.optBoolean("prerelease", false)
            if (prerelease && !includePrereleases) return@mapNotNull null
            val version = Regex("^afutube-v(\\d+\\.\\d+\\.\\d+(?:-[0-9A-Za-z.-]+)?)$").find(tag)?.groupValues?.get(1)
                ?: return@mapNotNull null
            val assets = release.optJSONArray("assets") ?: return@mapNotNull null
            var apkUrl = ""
            var checksumUrl = ""
            for (assetIndex in 0 until assets.length()) {
                val asset = assets.optJSONObject(assetIndex) ?: continue
                when (asset.optString("name")) {
                    "AfuTube-universal.apk" -> apkUrl = asset.optString("browser_download_url")
                    "AfuTube-universal.apk.sha256" -> checksumUrl = asset.optString("browser_download_url")
                }
            }
            if (apkUrl.isBlank() || checksumUrl.isBlank()) return@mapNotNull null
            AppUpdate(version, AppVersion.code(version), release.optString("body"), apkUrl, checksumUrl, prerelease = prerelease)
        }
        return candidates.maxByOrNull { it.versionCode }?.takeIf { it.versionCode > currentVersionCode }
    }
}

object Sha256 {
    fun verify(file: java.nio.file.Path, expected: String): Boolean =
        verify(file.toFile(), expected)

    fun verify(file: File, expected: String): Boolean {
        val actual = MessageDigest.getInstance("SHA-256").digest(file.readBytes())
            .joinToString("") { "%02x".format(it) }
        return actual.equals(expected.trim().split(Regex("\\s")).firstOrNull().orEmpty(), ignoreCase = true)
    }
}

object UpdateManager {
    private const val API = "https://api.github.com/repos/pirncedark/AfuDM/releases"
    private const val PREFS = "afutube_updates"
    private const val AUTO = "auto_check"
    private const val LAST_CHECK = "last_check"
    private const val DAY_MS = 24L * 60 * 60 * 1000
    private const val INCLUDE_PRERELEASES = "include_prereleases"

    suspend fun check(currentVersionCode: Int, includePrereleases: Boolean = false): AppUpdate? = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
        val connection = URL(API).openConnection() as HttpURLConnection
        connection.setRequestProperty("Accept", "application/vnd.github+json")
        connection.connectTimeout = 10_000
        connection.readTimeout = 15_000
        connection.inputStream.bufferedReader().use { AppUpdateParser.latest(it.readText(), currentVersionCode, includePrereleases) }
    }

    fun autoCheckEnabled(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        .getBoolean(AUTO, true)

    fun setAutoCheckEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(AUTO, enabled).apply()
    }

    fun shouldCheckAutomatically(context: Context): Boolean =
        autoCheckEnabled(context) && System.currentTimeMillis() - context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getLong(LAST_CHECK, 0) >= DAY_MS

    fun markChecked(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        .edit().putLong(LAST_CHECK, System.currentTimeMillis()).apply()

    fun includePrereleases(context: Context): Boolean = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        .getBoolean(INCLUDE_PRERELEASES, false)

    fun setIncludePrereleases(context: Context, enabled: Boolean) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        .edit().putBoolean(INCLUDE_PRERELEASES, enabled).apply()

    fun enqueueDownload(context: Context, update: AppUpdate) {
        val data = Data.Builder().putString("apkUrl", update.apkUrl).putString("checksumUrl", update.checksumUrl).build()
        val request = OneTimeWorkRequestBuilder<ApkDownloadWorker>().setInputData(data).build()
        WorkManager.getInstance(context).enqueue(request)
    }
}

class ApkDownloadWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = runCatching {
        val apk = File(applicationContext.cacheDir, "AfuTube-update.apk")
        download(inputData.getString("apkUrl")!!, apk)
        val checksum = URL(inputData.getString("checksumUrl")!!).openStream().bufferedReader().use { it.readText() }
        check(Sha256.verify(apk, checksum)) { "İndirilen dosyanın güvenlik özeti doğrulanamadı." }
        install(apk)
        Result.success()
    }.getOrElse { Result.failure(Data.Builder().putString("error", it.localizedMessage ?: "Güncelleme indirilemedi.").build()) }

    private fun download(url: String, target: File) {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.connectTimeout = 15_000
        connection.readTimeout = 60_000
        connection.inputStream.use { input -> target.outputStream().use { output -> input.copyTo(output) } }
    }

    private fun install(apk: File) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !applicationContext.packageManager.canRequestPackageInstalls()) {
            val intent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${applicationContext.packageName}"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            applicationContext.startActivity(intent)
            return
        }
        val uri = FileProvider.getUriForFile(applicationContext, "${applicationContext.packageName}.fileprovider", apk)
        val intent = Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        applicationContext.startActivity(intent)
    }
}
