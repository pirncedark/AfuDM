package com.afudm.afutube.updater

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.content.FileProvider
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ForegroundInfo
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import org.json.JSONArray
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.io.IOException
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
    const val ARM64_ABI = "arm64-v8a"
    const val ARM64_APK = "AfuTube-arm64-v8a.apk"
    const val UNIVERSAL_APK = "AfuTube-universal.apk"

    fun fromManifest(json: String, currentVersionCode: Int, supportedAbis: List<String>): AppUpdate? {
        val manifest = org.json.JSONObject(json)
        val version = manifest.getString("versionName")
        val code = manifest.getInt("versionCode")
        val tag = manifest.getString("tag")
        require(Regex("^afutube-v(\\d+\\.\\d+\\.\\d+(?:-[0-9A-Za-z.-]+)?)$").matches(tag))
        if (code <= currentVersionCode) return null
        val apk = if (ARM64_ABI in supportedAbis) ARM64_APK else UNIVERSAL_APK
        val base = "https://github.com/pirncedark/AfuDM/releases/download/$tag/$apk"
        return AppUpdate(version, code, manifest.optString("changelog"), base, "$base.sha256",
            minSdk = manifest.optInt("minSdk", 24), sha256 = manifest.optString("sha256"), prerelease = manifest.optBoolean("prerelease"))
    }

    fun shouldFallbackToApi(includePrereleases: Boolean, manifestReadSucceeded: Boolean): Boolean =
        includePrereleases || !manifestReadSucceeded

    fun checkErrorMessage(error: Throwable): String {
        val message = generateSequence(error) { it.cause }.joinToString(" ") { it.message.orEmpty() }
        return when {
            Regex("403|429|rate.?limit", RegexOption.IGNORE_CASE).containsMatchIn(message) -> "GitHub şu an yoğun, birkaç dakika sonra tekrar dene."
            error is java.net.UnknownHostException || error is java.net.ConnectException || error is java.net.SocketTimeoutException -> "İnternet bağlantısı yok."
            else -> "Güncelleme denetlenemedi."
        }
    }

    /**
     * [supportedAbis] Build.SUPPORTED_ABIS: cihaz arm64 destekliyorsa ve release'de arm64 APK varsa o secilir
     * (daha kucuk indirme); yoksa universal APK'ya dusulur.
     */
    fun latest(
        json: String,
        currentVersionCode: Int,
        includePrereleases: Boolean = false,
        supportedAbis: List<String> = emptyList()
    ): AppUpdate? {
        val releases = JSONArray(json)
        val candidates = (0 until releases.length()).mapNotNull { index ->
            val release = releases.optJSONObject(index) ?: return@mapNotNull null
            val tag = release.optString("tag_name")
            val prerelease = release.optBoolean("prerelease", false)
            if (prerelease && !includePrereleases) return@mapNotNull null
            val version = Regex("^afutube-v(\\d+\\.\\d+\\.\\d+(?:-[0-9A-Za-z.-]+)?)$").find(tag)?.groupValues?.get(1)
                ?: return@mapNotNull null
            val assets = release.optJSONArray("assets") ?: return@mapNotNull null
            val urls = (0 until assets.length()).mapNotNull { assetIndex ->
                val asset = assets.optJSONObject(assetIndex) ?: return@mapNotNull null
                asset.optString("name") to asset.optString("browser_download_url")
            }.toMap()
            val preferred = if (ARM64_ABI in supportedAbis) listOf(ARM64_APK, UNIVERSAL_APK) else listOf(UNIVERSAL_APK)
            val apkName = preferred.firstOrNull { !urls[it].isNullOrBlank() && !urls["$it.sha256"].isNullOrBlank() }
                ?: return@mapNotNull null
            val apkUrl = urls.getValue(apkName)
            val checksumUrl = urls.getValue("$apkName.sha256")
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
    private const val MANIFEST = "https://github.com/pirncedark/AfuDM/releases/download/afutube-latest/AfuTube-update.json"
    private const val PREFS = "afutube_updates"
    private const val AUTO = "auto_check"
    private const val LAST_CHECK = "last_check"
    private const val DAY_MS = 24L * 60 * 60 * 1000
    private const val INCLUDE_PRERELEASES = "include_prereleases"

    suspend fun check(currentVersionCode: Int, includePrereleases: Boolean = false): AppUpdate? = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
        var manifestRead = false
        if (!includePrereleases) {
            try {
                val manifest = fetchText(MANIFEST)
                manifestRead = true
                AppUpdateParser.fromManifest(manifest, currentVersionCode, Build.SUPPORTED_ABIS.toList())?.let { return@withContext it }
                return@withContext null
            } catch (_: Exception) { /* API fallback below */ }
        }
        check(AppUpdateParser.shouldFallbackToApi(includePrereleases, manifestRead))
        try {
            val releases = open("$API?per_page=100")
            releases.setRequestProperty("Accept", "application/vnd.github+json")
            AppUpdateParser.latest(read(releases), currentVersionCode, includePrereleases, Build.SUPPORTED_ABIS.toList())
        } catch (error: Exception) { throw IOException(AppUpdateParser.checkErrorMessage(error)) }
    }

    private fun open(url: String): HttpURLConnection = (URL(url).openConnection() as HttpURLConnection).apply {
        instanceFollowRedirects = true
        connectTimeout = 10_000
        readTimeout = 15_000
    }

    private fun fetchText(url: String): String = read(open(url))

    private fun read(connection: HttpURLConnection): String {
        val code = connection.responseCode
        if (code !in 200..299) throw IOException("HTTP $code")
        return connection.inputStream.bufferedReader().use { it.readText() }
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
    override suspend fun getForegroundInfo(): ForegroundInfo = progressInfo(0)

    override suspend fun doWork(): Result = runCatching {
        // On plan: 70-120 MB indirme uygulamadan cikilsa da surer; bildirimde yuzde gorunur.
        runCatching { setForeground(progressInfo(0)) }
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
        val total = connection.contentLengthLong
        var done = 0L
        var lastPercent = -1
        connection.inputStream.use { input ->
            target.outputStream().use { output ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    output.write(buffer, 0, read)
                    done += read
                    val percent = if (total > 0) (done * 100 / total).toInt() else 0
                    if (percent != lastPercent) {
                        lastPercent = percent
                        runCatching { setForegroundAsync(progressInfo(percent)) }
                    }
                }
            }
        }
    }

    private fun progressInfo(percent: Int): ForegroundInfo {
        val manager = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(PROGRESS_CHANNEL, "AfuTube güncelleme indirme", NotificationManager.IMPORTANCE_LOW)
            )
        }
        val notification = NotificationCompat.Builder(applicationContext, PROGRESS_CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("AfuTube güncellemesi indiriliyor")
            .setContentText("%$percent")
            .setProgress(100, percent, percent == 0)
            .setOngoing(true)
            .setSilent(true)
            .build()
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ForegroundInfo(PROGRESS_NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            ForegroundInfo(PROGRESS_NOTIFICATION_ID, notification)
        }
    }

    /**
     * Uygulama on plandaysa kurulum ekrani hemen acilir. Arka plandaysa (Android 10+ arka plandan ekran acmayi engeller)
     * "Kurmak icin dokun" bildirimi kalir; dokununca kurulum baslar. Bilinmeyen kaynak izni yoksa sistem kurucusu
     * izni kendisi sorar ve kuruluma geri doner, bu yuzden ayarlara ayrica yonlendirmiyoruz.
     */
    private fun install(apk: File) {
        val uri = FileProvider.getUriForFile(applicationContext, "${applicationContext.packageName}.fileprovider", apk)
        val intent = Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        notifyReadyToInstall(intent)
        runCatching { applicationContext.startActivity(intent) }
    }

    private fun notifyReadyToInstall(intent: Intent) {
        val manager = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(INSTALL_CHANNEL, "AfuTube güncellemeleri", NotificationManager.IMPORTANCE_HIGH)
            )
        }
        val pending = PendingIntent.getActivity(
            applicationContext, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = NotificationCompat.Builder(applicationContext, INSTALL_CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentTitle("AfuTube güncellemesi hazır")
            .setContentText("Kurmak için dokunun. Verileriniz silinmez.")
            .setContentIntent(pending)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
        runCatching { manager.notify(INSTALL_NOTIFICATION_ID, notification) }
    }

    private companion object {
        const val INSTALL_CHANNEL = "afutube_update_install"
        const val INSTALL_NOTIFICATION_ID = 7201
        const val PROGRESS_CHANNEL = "afutube_update_progress"
        const val PROGRESS_NOTIFICATION_ID = 7202
    }
}
