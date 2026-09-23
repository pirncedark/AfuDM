package com.afudm.afutube.downloader

import android.content.Context
import androidx.work.Constraints
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkInfo
import androidx.work.WorkManager
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import java.io.File
import java.util.UUID

/**
 * İndirme motorunun dış arayüzü.
 * ViewModel'lar yalnızca bu sınıfla konuşur.
 */
class DownloadEngine(private val context: Context) {

    private val workManager = WorkManager.getInstance(context)
    private val prefs = context.getSharedPreferences("afutube_downloads", Context.MODE_PRIVATE)
    private val hidden = MutableStateFlow(prefs.getStringSet(HIDDEN_KEY, emptySet()).orEmpty().toSet())

    data class DownloadRequest(
        val url       : String,
        val formatId  : String  = "",
        val title     : String,
        val outputDir : String? = null,
        val mergeAV   : Boolean = true,
        val audioFormat: String  = "",
        val embedThumbnail: Boolean = false,
        val embedChapters: Boolean = false
    )

    /** İndirmeyi kuyruğa ekler, WorkRequest ID'sini döndürür */
    fun enqueue(request: DownloadRequest): UUID {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val inputData = Data.Builder()
            .putString(DownloadWorker.KEY_URL, request.url)
            .putString(DownloadWorker.KEY_FORMAT_ID, request.formatId.ifBlank { "bestvideo+bestaudio/best" })
            .putBoolean(DownloadWorker.KEY_MERGE, request.mergeAV)
            .putString(DownloadWorker.KEY_AUDIO_FORMAT, request.audioFormat)
            .putBoolean(DownloadWorker.KEY_EMBED_THUMBNAIL, request.embedThumbnail)
            .putBoolean(DownloadWorker.KEY_EMBED_CHAPTERS, request.embedChapters)
            .apply { request.outputDir?.let { putString(DownloadWorker.KEY_OUTPUT_DIR, it) } }
            .build()
        val workRequest = OneTimeWorkRequestBuilder<DownloadWorker>()
            .setInputData(inputData)
            .setConstraints(constraints)
            .addTag("afutube_download")
            .addTag("title:${request.title.take(50)}")
            .build()

        workManager.enqueueUniqueWork(
            "download:${request.url.hashCode()}",
            ExistingWorkPolicy.KEEP,
            workRequest
        )
        return workRequest.id
    }

    /** Belirli bir indirmenin ilerleme akışı */
    fun progressOf(workId: UUID): Flow<DownloadProgress> =
        workManager.getWorkInfoByIdFlow(workId).map { info ->
            if (info == null) return@map DownloadProgress.idle()
            DownloadProgress(
                state   = info.state,
                percent = info.progress.getInt(DownloadWorker.PROGRESS_PERCENT, 0),
                speed   = info.progress.getString(DownloadWorker.PROGRESS_SPEED) ?: "",
                eta     = info.progress.getLong(DownloadWorker.PROGRESS_ETA, 0),
                size    = info.progress.getString(DownloadWorker.PROGRESS_SIZE) ?: "",
                error   = info.outputData.getString("error") ?: ""
            )
        }

    /** Tüm aktif HTTP indirme akışı */
    fun allDownloads(): Flow<List<WorkInfo>> =
        workManager.getWorkInfosByTagFlow("afutube_download")
            .combine(hidden) { infos, gizli -> infos.filterNot { it.id.toString() in gizli } }

    /**
     * Kaydi listeden kaldirir. Bitmemis / hatali indirmede isi iptal eder ve yarim kalan gecici
     * dosyalari (.part/.ytdl/.aria2/.temp) siler. Tamamlanmis indirmenin videosu SILINMEZ.
     */
    fun remove(workId: UUID, title: String, finished: Boolean) {
        if (!finished) {
            cancel(workId)
            deletePartialFiles(title)
        }
        val yeni = hidden.value + workId.toString()
        hidden.value = yeni
        prefs.edit().putStringSet(HIDDEN_KEY, yeni).apply()
    }

    private fun deletePartialFiles(title: String) {
        val dir = context.getExternalFilesDir(null) ?: return
        val prefix = title.take(20)
        if (prefix.isBlank()) return
        dir.listFiles()?.filter { f ->
            f.name.startsWith(prefix) && PARTIAL_SUFFIXES.any { f.name.contains(it) }
        }?.forEach { runCatching { it.delete() } }
    }

    fun cancel(workId: UUID) = workManager.cancelWorkById(workId)

    /** Cancel without deleting yt-dlp's partial files. */
    fun pause(workId: UUID) = workManager.cancelWorkById(workId)

    /** Recreate a stopped request with the same input so yt-dlp can continue its .part file. */
    fun resume(info: WorkInfo): UUID = requeue(info)

    /** Retry a failed request with its original options. */
    fun retry(info: WorkInfo): UUID = requeue(info)

    private fun requeue(info: WorkInfo): UUID {
        val request = OneTimeWorkRequestBuilder<DownloadWorker>()
            .setInputData(Data.Builder().putAll(info.inputData).build())
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .addTag("afutube_download")
            .addTag("title:${info.tags.firstOrNull { it.startsWith("title:") }?.removePrefix("title:") ?: "Download"}")
            .build()
        val url = info.inputData.getString(DownloadWorker.KEY_URL).orEmpty()
        workManager.enqueueUniqueWork("download:${url.hashCode()}", ExistingWorkPolicy.REPLACE, request)
        return request.id
    }

    /** Tüm HTTP indirmeleri durdur */
    fun cancelAll() = workManager.cancelAllWorkByTag("afutube_download")

    /**
     * Başarısız / iptal edilmiş bir indirmenin geçici dosyasını sil.
     * @param workId     WorkRequest ID'si (iptal için)
     * @param tempPath   Silinecek dosyanın tam yolu (boş olabilir)
     */
    fun cleanupFailedDownload(workId: UUID, tempPath: String) {
        cancel(workId)
        deleteFileIfExists(tempPath)
    }

    /** Belirtilen dosyayı sil; yoksa sessizce geç */
    fun deleteFileIfExists(path: String): Boolean {
        if (path.isBlank()) return true
        return try {
            val f = File(path)
            if (f.exists()) f.delete() else true
        } catch (e: Exception) {
            false
        }
    }

    companion object {
        private const val HIDDEN_KEY = "hidden_work_ids"
        private val PARTIAL_SUFFIXES = listOf(".part", ".ytdl", ".aria2", ".temp")

        @Volatile private var INSTANCE: DownloadEngine? = null
        fun getInstance(context: Context): DownloadEngine =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: DownloadEngine(context.applicationContext).also { INSTANCE = it }
            }
    }
}

data class DownloadProgress(
    val state   : WorkInfo.State,
    val percent : Int,
    val speed   : String,
    val eta     : Long,
    val size    : String,
    val error   : String
) {
    val isRunning  get() = state == WorkInfo.State.RUNNING
    val isFinished get() = state == WorkInfo.State.SUCCEEDED
    val isFailed   get() = state == WorkInfo.State.FAILED

    companion object {
        fun idle() = DownloadProgress(WorkInfo.State.ENQUEUED, 0, "", 0, "", "")
    }
}
