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
import com.afudm.afutube.updater.DownloadRecoveryPolicy
import com.afudm.afutube.updater.ExtractorUpdater
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

        const val KEY_AUDIO_FORMAT = "audio_format"
        const val KEY_HEADERS = "headers"
        const val KEY_TITLE = "title"
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
        val audioFormat = params.inputData.getString(KEY_AUDIO_FORMAT)?.lowercase()
        val headerPairs = params.inputData.getStringArray(KEY_HEADERS).orEmpty().toList().chunked(2)
            .filter { it.size == 2 && it[0].matches(Regex("[A-Za-z0-9-]{1,64}")) && it[1].length <= 8192 }
        val outputRoot = java.io.File(outputDir)
        val requestedTitle = params.inputData.getString(KEY_TITLE).orEmpty()
        val before = outputRoot.listFiles()?.associate { it.absolutePath to (it.lastModified() to it.length()) }.orEmpty()

        val pathFile = java.io.File(applicationContext.cacheDir, "afutube-path-$id.txt").apply { delete() }

        setForeground(createForegroundInfo("Hazırlanıyor…", 0))

        fun request(useAria2c: Boolean) = YoutubeDLRequest(url).apply {
            addOption("-f", formatId)
            val safeTitle = requestedTitle.replace(Regex("[\\\\/:*?\"<>|\\r\\n]"), "_").trim().take(100)
            addOption("-o", if (headerPairs.isNotEmpty() && safeTitle.isNotBlank()) "$outputDir/$safeTitle.%(ext)s" else "$outputDir/%(title)s.%(ext)s")
            headerPairs.forEach { (name, value) -> addOption("--add-header", "$name:$value") }
            // --print yt-dlp'yi sessiz moda sokar (ilerleme kaybolur); dosya yolu ayri dosyaya yazilir.
            addCommands(listOf("--print-to-file", "after_move:filepath", pathFile.absolutePath))
            addOption("--no-playlist")
            if (audioFormat != null) {
                addOption("-x")
                addOption("--audio-format", audioFormat)
                addOption("--audio-quality", "0")
            } else if (mergeAV) {
                addOption("--merge-output-format", "mp4")
                // Tek dosyali kaynak webm/mkv gelirse de sonuc MP4 olsun.
                addOption("--remux-video", "mp4")
            }
            if (useAria2c) {
                addOption("--external-downloader", "aria2c")
                addOption("--external-downloader-args", "aria2c:-x 8 -s 8 -k 5M")
            }
        }

        var lastPercent = 0

        fun onProgress(progress: Float, etaInSeconds: Long, line: String) {
            val percent = progress.toInt().coerceIn(0, 100)
            if (percent != lastPercent) {
                lastPercent = percent
                setProgressAsync(workDataOf(
                    PROGRESS_PERCENT to percent,
                    PROGRESS_ETA to etaInSeconds,
                    PROGRESS_SPEED to extractSpeed(line),
                    PROGRESS_SIZE to extractSize(line)
                ))
                setForegroundAsync(createForegroundInfo("$percent%  \u2022  ${extractSpeed(line)}", percent))
            }
        }

        val youtube = DownloadRecoveryPolicy.isYoutubeUrl(url)
        val firstStep = if (youtube) DownloadRecoveryPolicy.Step.LOCAL else DownloadRecoveryPolicy.Step.ARIA2C
        var finalError = ""
        var success = false
        var steps = listOf(firstStep)
        var index = 0
        while (index < steps.size) {
            if (isStopped) return@withContext Result.failure(workDataOf("error" to "\u0130ndirme iptal edildi"))
            val step = steps[index]
            if (step == DownloadRecoveryPolicy.Step.UPDATE_ENGINE) {
                setProgressAsync(workDataOf(PROGRESS_PERCENT to lastPercent, PROGRESS_SPEED to "Yeniden deneniyor\u2026"))
                setForeground(createForegroundInfo("Yeniden deneniyor\u2026", lastPercent))
                ExtractorUpdater.checkAndUpdate(applicationContext, force = true)
                index++
                continue
            }
            if (index > 0) {
                pathFile.delete()
                setProgressAsync(workDataOf(PROGRESS_PERCENT to lastPercent, PROGRESS_SPEED to "Yeniden deneniyor\u2026"))
                setForeground(createForegroundInfo("Yeniden deneniyor\u2026", lastPercent))
            }
            try {
                val response = YoutubeDL.getInstance().execute(request(step == DownloadRecoveryPolicy.Step.ARIA2C), callback = ::onProgress)
                finalError = response.err.orEmpty()
                if (response.exitCode == 0) { success = true; break }
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: YoutubeDL.CanceledException) {
                return@withContext Result.failure(workDataOf("error" to "\u0130ndirme iptal edildi"))
            } catch (e: Exception) {
                finalError = e.message.orEmpty()
            }
            if (!DownloadRecoveryPolicy.isHttp403(finalError)) break
            if (index == 0) steps = DownloadRecoveryPolicy.steps(youtube, initialHttp403 = true)
            index++
        }

        if (success) {
            val printedPath = runCatching { pathFile.readLines() }.getOrNull()
                ?.map { it.trim() }?.lastOrNull { it.isNotBlank() }
            pathFile.delete()
            val outputFile = printedPath?.let { java.io.File(it) }?.takeIf { it.isFile }
                ?: outputRoot.listFiles()?.asSequence()
                    ?.filter { file ->
                        file.isFile && file.name !in setOf(".", "..") &&
                            listOf(".part", ".ytdl", ".temp", ".aria2").none { file.name.endsWith(it, true) } &&
                            (before[file.absolutePath] == null || before[file.absolutePath] != (file.lastModified() to file.length()))
                    }
                    ?.maxByOrNull { it.lastModified() }
            if (outputFile != null) Result.success(workDataOf("output_path" to outputFile.absolutePath))
            else Result.failure(workDataOf("error" to "İndirme tamamlandı ancak dosya yolu bulunamadı"))
        } else {
            val error = if (youtube && DownloadRecoveryPolicy.isHttp403(finalError))
                "YouTube bu videoyu \u015fu an vermiyor (403). Biraz sonra tekrar dene.\n${okunurHata(finalError, headerPairs.map { it[1] })}"
            else okunurHata(finalError, headerPairs.map { it[1] })
            Result.failure(workDataOf("error" to error))
        }
    }

    /** yt-dlp stderr'inden kartta gosterilecek kisa neden (son ERROR satiri). */
    private fun okunurHata(err: String?, sensitiveValues: List<String> = emptyList()): String {
        var safeErr = err.orEmpty()
        sensitiveValues.filter(String::isNotEmpty).forEach { safeErr = safeErr.replace(it, "[gizli]") }
        val satirlar = safeErr.lines().map { it.trim() }.filter { it.isNotBlank() }
        val neden = satirlar.lastOrNull { it.startsWith("ERROR:") }?.removePrefix("ERROR:")?.trim()
            ?: satirlar.lastOrNull()
        return neden?.take(300)?.ifBlank { null } ?: "İndirme başarısız (yt-dlp ayrıntı vermedi)"
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
