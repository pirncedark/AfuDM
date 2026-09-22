package com.afudm.afutube.downloader

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.yausername.youtubedl_android.YoutubeDL
import com.yausername.youtubedl_android.YoutubeDLRequest
import kotlinx.coroutines.Dispatchers
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
        const val KEY_FORMAT_ID  = "format_id"
        const val KEY_OUTPUT_DIR = "output_dir"
        const val KEY_MERGE      = "merge_av"   // video+audio ayrı stream → FFmpeg merge

        const val PROGRESS_PERCENT = "progress_percent"
        const val PROGRESS_SPEED   = "progress_speed"
        const val PROGRESS_ETA     = "progress_eta"
        const val PROGRESS_SIZE    = "progress_size"

        private const val NOTIF_CHANNEL = "afutube_download"
        private const val NOTIF_ID      = 1001
    }

    override suspend fun getForegroundInfo(): ForegroundInfo =
        createForegroundInfo("İndiriliyor…", 0)

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val url       = params.inputData.getString(KEY_URL)       ?: return@withContext Result.failure()
        val formatId  = params.inputData.getString(KEY_FORMAT_ID) ?: "bestvideo+bestaudio/best"
        val outputDir = params.inputData.getString(KEY_OUTPUT_DIR)
            ?: applicationContext.getExternalFilesDir(null)?.absolutePath
            ?: return@withContext Result.failure()
        val mergeAV   = params.inputData.getBoolean(KEY_MERGE, true)

        setForeground(createForegroundInfo("Hazırlanıyor…", 0))

        val request = YoutubeDLRequest(url).apply {
            addOption("-f", formatId)
            addOption("-o", "$outputDir/%(title)s.%(ext)s")
            addOption("--no-playlist")
            if (mergeAV) {
                addOption("--merge-output-format", "mp4")
            }
            addOption("--external-downloader", "aria2c")
            addOption("--external-downloader-args", "aria2c:-x 8 -s 8 -k 5M")
        }

        var lastPercent = 0

        val response = YoutubeDL.getInstance().execute(request) { progress, etaInSeconds, line ->
            val percent = progress.toInt().coerceIn(0, 100)
            if (percent != lastPercent) {
                lastPercent = percent
                setProgressAsync(
                    workDataOf(
                        PROGRESS_PERCENT to percent,
                        PROGRESS_ETA     to etaInSeconds,
                        PROGRESS_SPEED   to extractSpeed(line),
                        PROGRESS_SIZE    to extractSize(line)
                    )
                )
                val fi = createForegroundInfo("$percent%  •  ${extractSpeed(line)}", percent)
                setForegroundAsync(fi)
            }
        }

        if (response.exitCode == 0) Result.success()
        else Result.failure(workDataOf("error" to response.err))
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
        return ForegroundInfo(NOTIF_ID, notif)
    }

    private fun createNotifChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIF_CHANNEL,
                "AfuTube Downloads",
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
