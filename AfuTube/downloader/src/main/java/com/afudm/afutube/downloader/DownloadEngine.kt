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
import kotlinx.coroutines.flow.map
import java.util.UUID

/**
 * İndirme motorunun dış arayüzü.
 * ViewModel'lar yalnızca bu sınıfla konuşur.
 */
class DownloadEngine(private val context: Context) {

    private val workManager = WorkManager.getInstance(context)

    data class DownloadRequest(
        val url       : String,
        val formatId  : String,
        val title     : String,
        val outputDir : String? = null,
        val mergeAV   : Boolean = true
    )

    /** İndirmeyi kuyruğa ekler, WorkRequest ID'sini döndürür */
    fun enqueue(request: DownloadRequest): UUID {
        val inputData = Data.Builder()
            .putString(DownloadWorker.KEY_URL,        request.url)
            .putString(DownloadWorker.KEY_FORMAT_ID,  request.formatId)
            .putBoolean(DownloadWorker.KEY_MERGE,     request.mergeAV)
            .apply {
                request.outputDir?.let { putString(DownloadWorker.KEY_OUTPUT_DIR, it) }
            }
            .build()

        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
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

    /** Tüm aktif indirme akışı */
    fun allDownloads(): Flow<List<WorkInfo>> =
        workManager.getWorkInfosByTagFlow("afutube_download")

    /** İndirmeyi durdur */
    fun cancel(workId: UUID) = workManager.cancelWorkById(workId)

    /** Tüm indirmeleri durdur */
    fun cancelAll() = workManager.cancelAllWorkByTag("afutube_download")

    companion object {
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
