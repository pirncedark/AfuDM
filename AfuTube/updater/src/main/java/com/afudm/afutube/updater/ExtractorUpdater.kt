package com.afudm.afutube.updater

import android.content.Context
import com.afudm.afutube.core.diagnostics.AnalysisErrorCategory
import com.afudm.afutube.runtime.MediaRuntime
import com.yausername.youtubedl_android.YoutubeDL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

object ExtractorUpdater {
    enum class Channel { STABLE, NIGHTLY }

    private const val PREFS = "afutube_extractor"
    private const val AUTO_UPDATE = "auto_update"
    private const val CHANNEL = "channel"
    private const val LAST_UPDATE = "last_update"
    private const val LAST_ATTEMPT = "last_attempt"

    private val coordinator = ExtractorUpdateCoordinator<Context>(
        version = { context ->
            MediaRuntime.withEngine {
                MediaRuntime.ensureInitialized(context)
                YoutubeDL.getInstance().versionName(context) ?: YoutubeDL.getInstance().version(context) ?: "bilinmiyor"
            }
        },
        update = { context, channel ->
            MediaRuntime.withEngine {
                if (channel == YoutubeDL.UpdateChannel.STABLE) {
                    runCatching { updateStableWithoutApi(context) }
                        .getOrElse { YoutubeDL.getInstance().updateYoutubeDL(context, channel) }
                } else YoutubeDL.getInstance().updateYoutubeDL(context, channel)
            }
        }
    )

    fun libraryChannel(channel: Channel): YoutubeDL.UpdateChannel = when (channel) {
        Channel.STABLE -> YoutubeDL.UpdateChannel.STABLE
        Channel.NIGHTLY -> YoutubeDL.UpdateChannel.NIGHTLY
    }

    suspend fun currentVersion(context: Context): String = withContext(Dispatchers.IO) {
        runCatching {
            MediaRuntime.withEngine {
                MediaRuntime.ensureInitialized(context.applicationContext)
                YoutubeDL.getInstance().versionName(context) ?: YoutubeDL.getInstance().version(context) ?: "bilinmiyor"
            }
        }.getOrElse { "hata: ${it.localizedMessage ?: "bilinmiyor"}" }
    }

    suspend fun checkAndUpdate(
        context: Context,
        channel: Channel = selectedChannel(context),
        force: Boolean = false,
        now: Long = System.currentTimeMillis()
    ): ExtractorUpdateResult = withContext(Dispatchers.IO) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val lastUpdate = prefs.getLong(LAST_UPDATE, 0L)
        if (!force && !ExtractorUpdatePolicy.isStale(lastUpdate, now)) {
            val current = currentVersion(context)
            return@withContext ExtractorUpdateResult(
                updated = false,
                oldVersion = current,
                newVersion = current,
                attempted = false
            )
        }

        val result = coordinator.update(context.applicationContext, channel, force = force, now = now)
        if (result.attempted) prefs.edit().putLong(LAST_ATTEMPT, now).apply()
        if (result.attempted && result.error.isBlank()) {
            prefs.edit()
                .putLong(LAST_UPDATE, now)
                .putString(CHANNEL, channel.name)
                .apply()
        }
        result
    }

    suspend fun maybeAutoUpdate(context: Context, now: Long = System.currentTimeMillis()): ExtractorUpdateResult? {
        if (!autoUpdateEnabled(context)) return null
        val lastAttempt = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(LAST_ATTEMPT, 0L)
        if (!ExtractorUpdatePolicy.canAutoRetry(lastAttempt, now)) return null
        return checkAndUpdate(context, selectedChannel(context), force = false, now = now)
    }

    fun shouldUpdateForAnalysis(context: Context, category: AnalysisErrorCategory, now: Long): Boolean {
        val lastUpdate = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(LAST_UPDATE, 0L)
        return ExtractorUpdatePolicy.shouldUpdateForAnalysis(category, lastUpdate, now)
    }

    fun lastUpdateAt(context: Context): Long =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(LAST_UPDATE, 0L)

    fun autoUpdateEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(AUTO_UPDATE, true)

    fun setAutoUpdateEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(AUTO_UPDATE, enabled).apply()
    }

    fun selectedChannel(context: Context): Channel =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(CHANNEL, Channel.STABLE.name)
            ?.let { runCatching { Channel.valueOf(it) }.getOrNull() }
            ?: Channel.STABLE

    fun setSelectedChannel(context: Context, channel: Channel) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(CHANNEL, channel.name).apply()
    }

    private fun updateStableWithoutApi(context: Context): YoutubeDL.UpdateStatus {
        val tag = readLatestStableTag() ?: error("GitHub release tag alınamadı")
        val youtubeDL = YoutubeDL.getInstance()
        if (tag == youtubeDL.version(context)) return YoutubeDL.UpdateStatus.ALREADY_UP_TO_DATE

        val temp = File.createTempFile("yt-dlp", ".download", context.cacheDir)
        try {
            val connection = URL("https://github.com/yt-dlp/yt-dlp/releases/latest/download/${YoutubeDL.ytdlpBin}")
                .openConnection().apply { connectTimeout = 15_000; readTimeout = 60_000 }
            connection.getInputStream().use { input -> temp.outputStream().use { output -> input.copyTo(output) } }
            require(temp.length() >= MIN_BINARY_BYTES) { "yt-dlp binary eksik veya çok küçük" }

            val directory = File(File(context.noBackupFilesDir, YoutubeDL.baseName), YoutubeDL.ytdlpDirName)
            check(directory.exists() || directory.mkdirs()) { "yt-dlp klasörü oluşturulamadı" }
            val binary = File(directory, YoutubeDL.ytdlpBin)
            val backup = File(directory, "${YoutubeDL.ytdlpBin}.previous")
            val staged = File(directory, "${YoutubeDL.ytdlpBin}.new")
            if (staged.exists()) check(staged.delete())
            temp.copyTo(staged, overwrite = true)
            check(staged.setExecutable(true, false) || staged.canExecute()) { "yt-dlp çalıştırılabilir yapılamadı" }
            if (backup.exists()) check(backup.delete())
            if (binary.exists()) check(binary.renameTo(backup)) { "Önceki yt-dlp binary yedeklenemedi" }
            try {
                check(staged.renameTo(binary)) { "Yeni yt-dlp binary kurulamadı" }
                context.getSharedPreferences(LIBRARY_PREFS, Context.MODE_PRIVATE).edit()
                    .putString("dlpVersion", tag).putString("dlpVersionName", tag).apply()
                backup.delete()
            } catch (error: Exception) {
                binary.delete()
                staged.delete()
                if (backup.exists()) backup.renameTo(binary)
                youtubeDL.init_ytdlp(context, directory)
                throw error
            }
            return YoutubeDL.UpdateStatus.DONE
        } finally { temp.delete() }
    }

    private fun readLatestStableTag(): String? {
        fun redirectLocation(method: String): String? {
            val connection = URL(STABLE_RELEASE_URL).openConnection() as HttpURLConnection
            return try {
                connection.instanceFollowRedirects = false
                connection.requestMethod = method
                connection.connectTimeout = 10_000
                connection.readTimeout = 10_000
                if (connection.responseCode in 300..399) connection.getHeaderField("Location") else null
            } finally { connection.disconnect() }
        }
        val location = runCatching { redirectLocation("HEAD") }.getOrNull()
            ?: redirectLocation("GET")
        return ExtractorUpdatePolicy.releaseTagFromLocation(location)
    }

    private const val MIN_BINARY_BYTES = 1_000_000L
    private const val STABLE_RELEASE_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest"
    private const val LIBRARY_PREFS = "youtubedl-android"
}
