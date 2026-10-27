package com.afudm.afutube.feature.editor.engine

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.workDataOf
import androidx.media3.common.util.UnstableApi
import androidx.media3.transformer.ExportException
import androidx.media3.transformer.ExportResult
import androidx.media3.transformer.ProgressHolder
import androidx.media3.transformer.Transformer
import com.afudm.afutube.downloader.DownloadFolder
import com.afudm.afutube.feature.editor.model.EditorProject
import java.io.File
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

@OptIn(UnstableApi::class)
class ExportWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val key = inputData.getString(KEY_PROJECT) ?: return Result.failure()
        val prefs = applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val json = prefs.getString(key, null) ?: return Result.failure()
        val project = runCatching { EditorProject.fromJson(json) }.getOrNull()?.takeIf { it.clips.isNotEmpty() } ?: return Result.failure()
        val quality = runCatching { ExportQuality.valueOf(inputData.getString(KEY_QUALITY) ?: "SOURCE") }.getOrDefault(ExportQuality.SOURCE)
        val first = project.clips.first()
        val sourceInfo = readSize(first.source)
        val target = CompositionPlanBuilder.build(project, sourceInfo.first, sourceInfo.second).outputSize
        val size = exportSize(target.width, target.height, quality)
        val composition = CompositionBuilder.build(project, CompositionPlan.OutputSize(size.width, size.height)).composition
        val sourceName = runCatching { File(Uri.parse(first.source).path ?: first.source).name }.getOrDefault("video")
        val outputName = exportFileName(sourceName, DownloadFolder.stagingDir(applicationContext).list()?.toList().orEmpty())
        val output = File(DownloadFolder.stagingDir(applicationContext), outputName)
        setForeground(createForegroundInfo(0))
        return try {
            val transformer = withContext(Dispatchers.Main.immediate) { Transformer.Builder(applicationContext).build() }
            val completion = CompletableDeferred<Boolean>()
            withContext(Dispatchers.Main.immediate) { transformer.addListener(object : Transformer.Listener {
                override fun onCompleted(composition: androidx.media3.transformer.Composition, exportResult: ExportResult) {
                    completion.complete(true)
                }
                override fun onError(composition: androidx.media3.transformer.Composition, exportResult: ExportResult, exportException: ExportException) {
                    completion.complete(false)
                }
            }); transformer.start(composition, output.absolutePath) }
            try {
                val holder = ProgressHolder()
                while (!completion.isCompleted) {
                    val available = withContext(Dispatchers.Main.immediate) { transformer.getProgress(holder) == Transformer.PROGRESS_STATE_AVAILABLE }
                    if (available) {
                        val percent = exportProgress(holder.progress)
                        setProgress(workDataOf("progress_percent" to percent))
                        setForeground(createForegroundInfo(percent))
                    }
                    delay(500)
                }
            } catch (cancelled: CancellationException) {
                withContext(Dispatchers.Main.immediate) { transformer.cancel() }
                throw cancelled
            }
            val success = completion.await()
            if (!success || !output.isFile || output.length() == 0L) {
                output.delete()
                prefs.edit().remove(key).apply()
                return Result.failure(workDataOf(KEY_ERROR to ERROR_MESSAGE))
            }
            val published = DownloadFolder.publish(applicationContext, output)
            prefs.edit().remove(key).apply()
            Result.success(workDataOf(KEY_OUTPUT to published, KEY_NAME to File(published).name))
        } catch (cancelled: CancellationException) {
            output.delete()
            prefs.edit().remove(key).apply()
            throw cancelled
        } catch (_: Exception) {
            output.delete()
            prefs.edit().remove(key).apply()
            Result.failure(workDataOf(KEY_ERROR to ERROR_MESSAGE))
        }
    }

    private fun readSize(source: String): Pair<Int, Int> = runCatching {
        MediaMetadataRetriever().useRetriever { retriever ->
            retriever.setDataSource(applicationContext, Uri.parse(source))
            val width = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)?.toIntOrNull() ?: 1920
            val height = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)?.toIntOrNull() ?: 1080
            width to height
        }
    }.getOrDefault(1920 to 1080)

    private fun createForegroundInfo(percent: Int): ForegroundInfo {
        val manager = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26) manager.createNotificationChannel(NotificationChannel(CHANNEL, "Video kaydı", NotificationManager.IMPORTANCE_LOW))
        val notification = NotificationCompat.Builder(applicationContext, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentTitle("Video kaydediliyor")
            .setContentText("$percent% tamamlandı")
            .setProgress(100, percent, false)
            .setOngoing(true)
            .build()
        return ForegroundInfo(NOTIFICATION_ID, notification)
    }

    companion object {
        const val KEY_PROJECT = "project_key"
        const val KEY_QUALITY = "quality"
        const val KEY_OUTPUT = "output_path"
        const val KEY_NAME = "output_name"
        const val KEY_ERROR = "error"
        const val ERROR_MESSAGE = "Video kaydedilemedi. Daha düşük kalitede tekrar dene."
        private const val PREFS = "editor_exports"
        private const val CHANNEL = "editor_export"
        private const val NOTIFICATION_ID = 7214
        private fun projectPrefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

        fun enqueue(context: Context, project: EditorProject, quality: ExportQuality): UUID {
            val key = UUID.randomUUID().toString()
            projectPrefs(context).edit().putString(key, project.toJson()).apply()
            val request = OneTimeWorkRequestBuilder<ExportWorker>()
                .setInputData(workDataOf(KEY_PROJECT to key, KEY_QUALITY to quality.name))
                .build()
            WorkManager.getInstance(context).enqueue(request)
            return request.id
        }
    }
}

private inline fun <T> MediaMetadataRetriever.useRetriever(block: (MediaMetadataRetriever) -> T): T = try { block(this) } finally { release() }
