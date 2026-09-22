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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import java.io.BufferedInputStream
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL

/**
 * WorkManager tabanlı torrent / magnet indirme worker'ı.
 *
 * Gerçek bir libtorrent bağımlılığı olmadığı için bu worker şu anda
 * torrent URI'sini bir HTTP URL gibi ele alır. Eğer URI "magnet:" ile
 * başlıyorsa hemen hata döndürür ve kullanıcıya açıklayıcı bir mesaj verir.
 *
 * Gelecekte com.github.jlibtorrent:jlibtorrent eklendiğinde buradaki
 * executeHttpFallback() yerine libtorrent session kodu gelecek.
 */
class TorrentWorker(
    appContext: Context,
    private val params: WorkerParameters
) : CoroutineWorker(appContext, params) {

    companion object {
        const val KEY_TORRENT_URI = "torrent_uri"
        const val KEY_OUTPUT_DIR  = "output_dir"
        const val KEY_TITLE       = "title"

        private const val NOTIF_CHANNEL = "afutube_torrent"
        private const val NOTIF_ID      = 2001
    }

    override suspend fun getForegroundInfo(): ForegroundInfo =
        buildForegroundInfo("Torrent bekleniyor…", 0)

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val uri = params.inputData.getString(KEY_TORRENT_URI)
            ?: return@withContext Result.failure(workDataOf("error" to "URI bulunamadı"))

        val title = params.inputData.getString(KEY_TITLE) ?: "Torrent"

        val outputDir = params.inputData.getString(KEY_OUTPUT_DIR)
            ?: applicationContext.getExternalFilesDir(null)?.absolutePath
            ?: applicationContext.filesDir.absolutePath

        setForeground(buildForegroundInfo("$title başlatılıyor…", 0))

        return@withContext when {
            uri.startsWith("magnet:", ignoreCase = true) -> {
                // Magnet linki — gelecekte libtorrent ile ele alınacak
                Result.failure(
                    workDataOf("error" to "Magnet bağlantıları şu anda desteklenmiyor. Lütfen .torrent dosyasını kullanın.")
                )
            }
            uri.startsWith("http://", ignoreCase = true) ||
            uri.startsWith("https://", ignoreCase = true) ||
            uri.startsWith("content://", ignoreCase = true) -> {
                downloadFile(uri, title, outputDir)
            }
            else -> {
                // Yerel dosya yolu (file:// veya düz yol)
                val file = File(uri.removePrefix("file://"))
                if (file.exists()) {
                    Result.success(workDataOf("output_path" to file.absolutePath))
                } else {
                    Result.failure(workDataOf("error" to "Dosya bulunamadı: $uri"))
                }
            }
        }
    }

    /** HTTP(S) üzerinden dosya indirir ve ilerlemeyi raporlar */
    private suspend fun downloadFile(
        url: String,
        title: String,
        outputDir: String
    ): Result = withContext(Dispatchers.IO) {
        try {
            val connection = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 15_000
                readTimeout    = 30_000
                connect()
            }

            val totalBytes = connection.contentLengthLong
            val outFile = File(outputDir, "${title.take(40)}.torrent")

            BufferedInputStream(connection.inputStream).use { input ->
                FileOutputStream(outFile).use { output ->
                    val buffer = ByteArray(8192)
                    var downloaded = 0L
                    var lastReported = -1

                    while (isActive) {
                        val read = input.read(buffer)
                        if (read == -1) break
                        output.write(buffer, 0, read)
                        downloaded += read

                        val percent = if (totalBytes > 0)
                            (downloaded * 100 / totalBytes).toInt().coerceIn(0, 100)
                        else 0

                        if (percent != lastReported) {
                            lastReported = percent
                            setProgress(workDataOf(
                                DownloadWorker.PROGRESS_PERCENT to percent,
                                DownloadWorker.PROGRESS_SIZE    to "${downloaded / 1024} KB",
                                DownloadWorker.PROGRESS_SPEED   to "",
                                DownloadWorker.PROGRESS_ETA     to 0L
                            ))
                            setForeground(buildForegroundInfo("$title  $percent%", percent))
                        }
                    }
                }
            }
            connection.disconnect()

            if (!isActive) {
                // İptal edildi — geçici dosyayı temizle
                outFile.delete()
                Result.failure(workDataOf("error" to "İndir iptal edildi"))
            } else {
                Result.success(workDataOf("output_path" to outFile.absolutePath))
            }
        } catch (e: Exception) {
            Result.failure(workDataOf("error" to (e.message ?: "Bilinmeyen hata")))
        }
    }

    private fun buildForegroundInfo(text: String, progress: Int): ForegroundInfo {
        createNotifChannel()
        val notif = NotificationCompat.Builder(applicationContext, NOTIF_CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("AfuTube — Torrent")
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
                "AfuTube Torrent",
                NotificationManager.IMPORTANCE_LOW
            )
            applicationContext
                .getSystemService(NotificationManager::class.java)
                .createNotificationChannel(channel)
        }
    }
}
