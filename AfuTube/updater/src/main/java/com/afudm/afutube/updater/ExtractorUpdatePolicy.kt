package com.afudm.afutube.updater

import com.afudm.afutube.core.diagnostics.AnalysisErrorCategory
import com.yausername.youtubedl_android.YoutubeDL
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

data class ExtractorUpdateResult(
    val updated: Boolean,
    val oldVersion: String,
    val newVersion: String,
    val attempted: Boolean = true,
    val error: String = ""
)

object ExtractorUpdatePolicy {
    const val DAY_MS = 24L * 60 * 60 * 1000

    fun isStale(lastUpdateAt: Long, now: Long): Boolean =
        lastUpdateAt <= 0L || now - lastUpdateAt >= DAY_MS

    fun shouldUpdateForAnalysis(category: AnalysisErrorCategory, lastUpdateAt: Long, now: Long): Boolean =
        category in setOf(
            AnalysisErrorCategory.EXTRACTOR,
            AnalysisErrorCategory.UNSUPPORTED,
            AnalysisErrorCategory.PARSE
        ) && isStale(lastUpdateAt, now)
}

class ExtractorUpdateCoordinator<C>(
    private val version: suspend (C) -> String,
    private val update: suspend (C, YoutubeDL.UpdateChannel) -> YoutubeDL.UpdateStatus?
) {
    private val mutex = Mutex()
    private var lastSuccessfulRunAt = 0L

    suspend fun update(
        context: C,
        channel: ExtractorUpdater.Channel,
        force: Boolean = false,
        now: Long = System.currentTimeMillis()
    ): ExtractorUpdateResult = mutex.withLock {
        if (!force && lastSuccessfulRunAt > 0L && !ExtractorUpdatePolicy.isStale(lastSuccessfulRunAt, now)) {
            val current = version(context)
            return@withLock ExtractorUpdateResult(
                updated = false,
                oldVersion = current,
                newVersion = current,
                attempted = false
            )
        }
        val oldVersion = version(context)
        runCatching { update(context, ExtractorUpdater.libraryChannel(channel)) }
            .fold(
                onSuccess = { status ->
                    lastSuccessfulRunAt = now
                    ExtractorUpdateResult(
                        updated = status == YoutubeDL.UpdateStatus.DONE,
                        oldVersion = oldVersion,
                        newVersion = version(context)
                    )
                },
                onFailure = { error ->
                    ExtractorUpdateResult(
                        updated = false,
                        oldVersion = oldVersion,
                        newVersion = oldVersion,
                        error = error.localizedMessage ?: "Güncelleme başarısız"
                    )
                }
            )
    }
}
