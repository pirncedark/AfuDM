package com.afudm.afutube.downloader

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.ServiceInfo
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import kotlinx.coroutines.Dispatchers
import com.afudm.afutube.runtime.MediaRuntime
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import android.net.Uri
import java.io.BufferedInputStream
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL

/** Torrent ve magnet içeriklerini uygulamanın mevcut aria2c motoruyla indirir. */
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
        private const val TAG = "AfuTubeTorrent"
    }

    override suspend fun getForegroundInfo(): ForegroundInfo =
        buildForegroundInfo("Torrent bekleniyor…", 0)

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val source = params.inputData.getString(KEY_TORRENT_URI)?.trim()
            ?.takeIf { it.isNotEmpty() }
            ?: return@withContext failure("Bağlantı bulunamadı, indirmeyi yeniden başlat.")
        val title = params.inputData.getString(KEY_TITLE) ?: "Torrent"
        val outputRoot = File(params.inputData.getString(KEY_OUTPUT_DIR)
            ?: DownloadFolder.stagingDir(applicationContext).absolutePath)
        // WorkManager retries reuse this directory; partial files and .aria2 stay intact.
        val destination = File(outputRoot, "torrent-$id")
        val temporary = File(applicationContext.cacheDir, "torrent-$id")
        val recentOutput = ArrayDeque<String>()
        var stage = "initialization"
        fun logFailure(message: String, error: Exception? = null) {
            Log.e(TAG, "work=$id stage=$stage $message\naria2c last 30 lines:\n${recentOutput.joinToString("\n")}", error)
        }
        try {
            Log.i(TAG, "work=$id worker started magnet=${source.startsWith("magnet:", true)}")
            setForeground(buildForegroundInfo("$title hazırlanıyor…", 0))
            val executable = File(applicationContext.applicationInfo.nativeLibraryDir, "libaria2c.so")
            if (!executable.isFile) {
                logFailure("Missing executable: $executable")
                return@withContext failure("İndirme bileşeni eksik, uygulamayı güncelleyip yeniden dene.")
            }
            if (!executable.canExecute()) {
                logFailure("Executable is not runnable: $executable")
                return@withContext failure("İndirme bileşeni çalıştırılamıyor, uygulamayı güncelleyip yeniden dene.")
            }
            MediaRuntime.ensureInitialized(applicationContext)
            check(destination.isDirectory || destination.mkdirs())
            check(temporary.isDirectory || temporary.mkdirs())
            val magnet = source.startsWith("magnet:", ignoreCase = true)
            stage = "input"
            val input = if (magnet) source else prepareTorrent(source, temporary).absolutePath
            if (magnet) {
                setProgress(workDataOf(
                    DownloadWorker.PROGRESS_PERCENT to 0,
                    DownloadWorker.PROGRESS_SIZE to "",
                    DownloadWorker.PROGRESS_SPEED to "Metadata alınıyor…",
                    DownloadWorker.PROGRESS_ETA to 0L
                ))
                setForeground(buildForegroundInfo("Metadata alınıyor…", 0))
            }
            val packages = File(applicationContext.noBackupFilesDir, "youtubedl-android/packages")
            val certificate = File(packages, "python/usr/etc/tls/cert.pem")
            val trackers = applicationContext.assets.open("torrent-trackers.txt").bufferedReader().use {
                parseTorrentTrackers(it.readText())
            }
            val builder = ProcessBuilder(torrentArguments(executable.absolutePath, destination.absolutePath,
                input, certificate.absolutePath, File(applicationContext.filesDir, "dht.dat").absolutePath, trackers))
                .directory(temporary).redirectErrorStream(true)
            // Match YoutubeDL 0.18.1's runtime paths, including its trusted certificate bundle.
            builder.environment()["LD_LIBRARY_PATH"] = listOf("python", "ffmpeg", "aria2c")
                .joinToString(":") { File(packages, "$it/usr/lib").absolutePath } +
                ":" + applicationContext.applicationInfo.nativeLibraryDir
            builder.environment()["SSL_CERT_FILE"] = certificate.absolutePath
            stage = "process"
            val process = builder.start()
            Log.i(TAG, "work=$id aria2c started trackers=${trackers.size}")
            val exitCode = coroutineScope {
                val lines = Channel<String>(32)
                val reader = launch(Dispatchers.IO) {
                    try {
                        process.inputStream.bufferedReader().use { stream ->
                            while (isActive) {
                                val line = stream.readLine() ?: break
                                lines.send(line)
                            }
                        }
                    } finally {
                        lines.close()
                    }
                }
                try {
                    for (line in lines) {
                        if (recentOutput.size == 30) recentOutput.removeFirst()
                        recentOutput.addLast(line)
                        ensureActive()
                        parseTorrentProgress(line)?.let { progress ->
                            // Metadata transfers also have a progress line, but no known total.
                            if (magnet && progress.totalUnknown) return@let
                            setProgress(workDataOf(
                                DownloadWorker.PROGRESS_PERCENT to progress.percent,
                                DownloadWorker.PROGRESS_SIZE to progress.size,
                                DownloadWorker.PROGRESS_SPEED to progress.speed,
                                DownloadWorker.PROGRESS_ETA to progress.etaSeconds
                            ))
                            setForeground(buildForegroundInfo("$title  ${progress.percent}%", progress.percent))
                        }
                    }
                    while (process.isAlive) delay(100)
                    ensureActive()
                    process.exitValue()
                } finally {
                    if (process.isAlive) process.destroyForcibly()
                    process.inputStream.close()
                    reader.cancel()
                }
            }
            ensureActive()
            Log.i(TAG, "work=$id aria2c exit=$exitCode")
            val files = destination.walkTopDown().filter { it.isFile }.toList()
            val payload = files.filter { file ->
                !file.name.endsWith(".aria2", true) && !file.name.endsWith(".torrent", true)
            }
            if (exitCode != 0 || payload.none { it.length() > 0 } ||
                files.any { it.name.endsWith(".aria2", true) }) {
                logFailure("exit=$exitCode payload=${payload.size} incomplete=${files.any { it.name.endsWith(".aria2", true) }}")
                failure("İndirme tamamlanamadı, bağlantıyı kontrol edip yeniden dene.")
            } else {
                stage = "publish"
                val outputPath = if (payload.size == 1) {
                    DownloadFolder.publish(applicationContext, payload.single())
                } else {
                    // Keep the complete torrent tree as the aggregate output. Publish copies
                    // so a failed public-folder write cannot split it across directories.
                    for (file in payload) {
                        ensureActive()
                        val copy = File(temporary, "publish/${file.name}")
                        try {
                            check(copy.parentFile!!.isDirectory || copy.parentFile!!.mkdirs())
                            file.copyTo(copy, overwrite = true)
                            val published = DownloadFolder.publish(applicationContext, copy)
                            check(published != copy.absolutePath) { "Could not publish ${file.name}" }
                        } finally {
                            copy.delete()
                        }
                    }
                    destination.absolutePath
                }
                Log.i(TAG, "work=$id publish complete files=${payload.size}")
                Result.success(workDataOf("output_path" to outputPath))
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            logFailure("Torrent failed", error)
            failure("İndirme başlatılamadı, bağlantıyı kontrol edip yeniden dene.")
        } finally {
            // Only the fetched descriptor is disposable; payload/.aria2 files allow resume.
            File(temporary, "input.torrent").delete()
        }
    }

    private fun failure(message: String): Result = Result.failure(workDataOf("error" to message))

    private suspend fun prepareTorrent(source: String, temporary: File): File {
        val uri = Uri.parse(source)
        val file = File(temporary, "input.torrent")
        when (uri.scheme?.lowercase()) {
            "http", "https" -> {
                val connection = (URL(source).openConnection() as HttpURLConnection).apply {
                    connectTimeout = 15_000
                    readTimeout = 30_000
                }
                try {
                    check(connection.responseCode in 200..299)
                    BufferedInputStream(connection.inputStream).use { input ->
                        FileOutputStream(file).use { output ->
                            val buffer = ByteArray(8192)
                            while (true) {
                                kotlin.coroutines.coroutineContext.ensureActive()
                                val read = input.read(buffer)
                                if (read == -1) break
                                output.write(buffer, 0, read)
                            }
                        }
                    }
                } finally {
                    connection.disconnect()
                }
            }
            "content" -> {
                val input = applicationContext.contentResolver.openInputStream(uri)
                    ?: error("Missing input")
                input.use {
                    FileOutputStream(file).use { output ->
                        val buffer = ByteArray(8192)
                        while (true) {
                            kotlin.coroutines.coroutineContext.ensureActive()
                            val read = it.read(buffer)
                            if (read == -1) break
                            output.write(buffer, 0, read)
                        }
                    }
                }
            }
            null, "file" -> {
                val local = File(if (uri.scheme == null) source else requireNotNull(uri.path))
                check(local.isFile && local.length() > 0)
                return local
            }
            else -> error("Unsupported input")
        }
        check(file.length() > 0)
        return file
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
                "AfuTube Torrent",
                NotificationManager.IMPORTANCE_LOW
            )
            applicationContext
                .getSystemService(NotificationManager::class.java)
                .createNotificationChannel(channel)
        }
    }
}


// Pure JVM helpers: no Android or coroutine types in their API.
internal data class TorrentProgress(
    val percent: Int,
    val size: String,
    val speed: String,
    val etaSeconds: Long,
    val totalUnknown: Boolean
)

internal fun parseTorrentProgress(line: String): TorrentProgress? {
    val match = Regex("""\[#\w+\s+(\d+(?:\.\d+)?[KMGTPE]?i?B)/(\d+(?:\.\d+)?[KMGTPE]?i?B)(?:\((\d+)%\))?[^\]]*]""")
        .find(line) ?: return null
    val summary = match.value
    val speed = Regex("""\bDL:([^\s\]]+)""").find(summary)?.groupValues?.get(1).orEmpty()
    val eta = Regex("""\bETA:([^\s\]]+)""").find(summary)?.groupValues?.get(1).orEmpty()
    val seconds = Regex("""(\d+)([dhms])""").findAll(eta).sumOf {
        it.groupValues[1].toLong() * when (it.groupValues[2]) {
            "d" -> 86400L
            "h" -> 3600L
            "m" -> 60L
            else -> 1L
        }
    }
    return TorrentProgress(
        match.groupValues[3].toIntOrNull()?.coerceIn(0, 100) ?: 0,
        "${match.groupValues[1]}/${match.groupValues[2]}",
        if (speed.isEmpty()) "" else "$speed/s",
        seconds,
        match.groupValues[2].takeWhile { it.isDigit() || it == '.' }.toDoubleOrNull() == 0.0
    )
}

internal fun parseTorrentTrackers(text: String): List<String> = text.lineSequence()
    .map(String::trim).filter { it.startsWith("udp://") || it.startsWith("https://") || it.startsWith("http://") }
    .filterNot { it.contains(',') || it.any(Char::isWhitespace) }.distinct().toList()

internal fun torrentArguments(executable: String, outputDir: String, source: String, certificate: String? = null,
    dhtPath: String? = null, trackers: List<String> = emptyList()): List<String> {
    require(source.isNotBlank() && !source.startsWith("-"))
    return listOf(executable, "--seed-time=0", "--bt-save-metadata=true", "--follow-torrent=true",
        "--enable-dht=true", "--bt-enable-lpd=true", "--enable-peer-exchange=true", "--bt-max-peers=0",
        "--file-allocation=none", "--summary-interval=1", "--console-log-level=notice",
        "--enable-color=false", "--show-console-readout=false", "--continue=true",
        "--dir=$outputDir") + listOfNotNull(certificate?.let { "--ca-certificate=$it" },
        dhtPath?.let { "--dht-file-path=$it" },
        trackers.takeIf { it.isNotEmpty() }?.let { "--bt-tracker=${it.joinToString(",")}" }) + source
}
