package com.afudm.afutube.downloader

import com.afudm.afutube.runtime.MediaRuntime
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.yausername.youtubedl_android.YoutubeDL
import com.yausername.youtubedl_android.YoutubeDLException
import com.yausername.youtubedl_android.YoutubeDLRequest
import com.afudm.afutube.updater.ExtractorUpdater
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * WorkManager tabanlı indirme worker'ı.
 * Foreground service olarak çalışır — Android pil optimizasyonlarından etkilenmez.
 */
class DownloadWorker(
    appContext: Context,
    private val params: WorkerParameters
) : CoroutineWorker(appContext, params) {

    companion object {
        const val KEY_URL        = "url"
        const val KEY_TITLE      = "title"
        const val KEY_FORMAT_ID  = "format_id"
        const val KEY_OUTPUT_DIR = "output_dir"
        const val KEY_AUDIO_FORMAT = "audio_format"
        const val KEY_EMBED_THUMBNAIL = "embed_thumbnail"
        const val KEY_EMBED_CHAPTERS = "embed_chapters"
        const val KEY_MERGE      = "merge_av"   // video+audio ayrı stream → FFmpeg merge

        const val PROGRESS_PERCENT = "progress_percent"
        const val PROGRESS_SPEED   = "progress_speed"
        const val PROGRESS_ETA     = "progress_eta"
        const val PROGRESS_SIZE    = "progress_size"

        private const val NOTIF_CHANNEL = "afutube_download"
        private const val NOTIF_ID      = 1001
    }

    override suspend fun getForegroundInfo(): ForegroundInfo =
        createForegroundInfo(applicationContext.getString(R.string.download_notification_downloading), 0)
    private val processId: String get() = params.id.toString()

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        try {
            MediaRuntime.ensureInitialized(applicationContext)
        } catch (error: MediaRuntime.MediaInitializationException) {
            return@withContext Result.failure(
                workDataOf("error" to (error.message ?: "Medya motoru başlatılamadı"))
            )
        }
        val url       = params.inputData.getString(KEY_URL)       ?: return@withContext Result.failure()
        val formatId  = params.inputData.getString(KEY_FORMAT_ID) ?: "bestvideo+bestaudio/best"
        val outputDir = params.inputData.getString(KEY_OUTPUT_DIR)
            ?: applicationContext.getExternalFilesDir(null)?.absolutePath
            ?: return@withContext Result.failure()
        val mergeAV   = params.inputData.getBoolean(KEY_MERGE, true)
        val audioFormat = params.inputData.getString(KEY_AUDIO_FORMAT).orEmpty()
        val rateLimit = applicationContext.getSharedPreferences("afutube_downloads", Context.MODE_PRIVATE)
            .getInt("rate_limit_kbps", 0)

        setForeground(createForegroundInfo(applicationContext.getString(R.string.download_notification_preparing), 0))

        val request = YoutubeDLRequest(url).apply {
            addOption("-f", formatId)
            addOption("-o", "$outputDir/%(title)s.%(ext)s")
            addOption("--no-playlist")
            DownloadPolicies.ytDlpOptions(
                audioFormat,
                params.inputData.getBoolean(KEY_EMBED_THUMBNAIL, false),
                params.inputData.getBoolean(KEY_EMBED_CHAPTERS, false),
                rateLimit
            ).forEach { (option, value) -> if (value == null) addOption(option) else addOption(option, value) }
            if (mergeAV) {
                addOption("--merge-output-format", "mp4")
            }
            addOption("--external-downloader", "aria2c")
            addOption("--external-downloader-args", "aria2c:-x 8 -s 8 -k 5M")
        }

        var lastPercent = 0

        var lastError = ""
        for (attempt in 0 until DownloadPolicies.MAX_HTTP_ATTEMPTS) {
            try {
                if (isStopped) throw CancellationException("Download stopped")
                val response = executeWithStopMonitoring(request) { progress, etaInSeconds, line ->
                    val percent = progress.toInt().coerceIn(0, 100)
                    if (percent != lastPercent) {
                        lastPercent = percent
                        setProgressAsync(workDataOf(
                            PROGRESS_PERCENT to percent,
                            PROGRESS_ETA to etaInSeconds,
                            PROGRESS_SPEED to extractSpeed(line),
                            PROGRESS_SIZE to extractSize(line)
                        ))
                        setForegroundAsync(createForegroundInfo(
                            applicationContext.getString(R.string.download_notification_progress, percent, extractSpeed(line)), percent
                        ))
                    }
                }
                if (response.exitCode == 0) return@withContext Result.success()
                lastError = response.err
            } catch (cancelled: CancellationException) {
                YoutubeDL.getInstance().destroyProcessById(processId)
                throw cancelled
            } catch (cancelled: YoutubeDL.CanceledException) {
                YoutubeDL.getInstance().destroyProcessById(processId)
                if (isStopped) throw CancellationException("Download stopped", cancelled)
                return@withContext Result.failure(workDataOf("error" to applicationContext.getString(R.string.download_cancelled)))
            } catch (error: YoutubeDLException) {
                lastError = error.message.orEmpty()
            }
            if (!DownloadPolicies.shouldRetryFailure(lastError, attempt, cancelled = isStopped)) break
            if (attempt == 0) runCatching {
                ExtractorUpdater.checkAndUpdate(
                    applicationContext,
                    ExtractorUpdater.selectedChannel(applicationContext),
                    force = true
                )
            }
            delay(DownloadPolicies.retryDelayMillis(attempt))
        }
        val userMessage = when {
            Regex("(^|\\D)403(\\D|$)").containsMatchIn(lastError) -> applicationContext.getString(R.string.youtube_403_download_error)
            Regex("(^|\\D)429(\\D|$)").containsMatchIn(lastError) -> applicationContext.getString(R.string.youtube_429_download_error)
            else -> lastError
        }
        Result.failure(workDataOf("error" to userMessage))
    }

    private suspend fun executeWithStopMonitoring(
        request: YoutubeDLRequest,
        callback: (Float, Long, String) -> Unit
    ) = withContext(Dispatchers.IO) {
        val watcher = CoroutineScope(Dispatchers.IO).launch {
            while (isActive) {
                if (isStopped) {
                    if (YoutubeDL.getInstance().destroyProcessById(processId)) break
                }
                delay(150)
            }
        }
        try {
            YoutubeDL.getInstance().execute(request, processId, false, callback)
        } finally {
            withContext(NonCancellable) { watcher.cancelAndJoin() }
        }
    }

    private fun createForegroundInfo(text: String, progress: Int): ForegroundInfo {
        createNotifChannel()
        val notif = NotificationCompat.Builder(applicationContext, NOTIF_CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("AfuTube İndiriyor")
            .setContentText(text)
            .setProgress(100, progress, progress == 0)
            .setOngoing(true)
            .setSilent(true)
            .build()
        // Android 14+ (targetSdk 34+): tur verilmeden baslatilan on plan servisi uygulamayi COKERTIR
        // ("uygulama durduruldu"). Manifestteki SystemForegroundService turu dataSync.
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ForegroundInfo(NOTIF_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            ForegroundInfo(NOTIF_ID, notif)
        }
    }

    private fun createNotifChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIF_CHANNEL,
                applicationContext.getString(R.string.download_notification_channel),
                NotificationManager.IMPORTANCE_LOW
            )
            applicationContext
                .getSystemService(NotificationManager::class.java)
                .createNotificationChannel(channel)
        }
    }

    private fun extractSpeed(line: String): String =
        Regex("""([\d.]+[KMG]iB/s)""").find(line)?.value ?: ""

    private fun extractSize(line: String): String =
        Regex("""(\d+\.?\d*\s*[KMG]iB)\s*/""").find(line)?.value?.trim() ?: ""
}
