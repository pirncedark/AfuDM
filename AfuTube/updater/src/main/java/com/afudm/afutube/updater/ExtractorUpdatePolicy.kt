package com.afudm.afutube.updater

import com.afudm.afutube.core.diagnostics.AnalysisErrorCategory
import com.yausername.youtubedl_android.YoutubeDL
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.net.URI

data class ExtractorUpdateResult(
    val updated: Boolean,
    val oldVersion: String,
    val newVersion: String,
    val attempted: Boolean = true,
    val error: String = ""
)

object ExtractorUpdatePolicy {
    const val DAY_MS = 24L * 60 * 60 * 1000
    const val RETRY_MS = 60L * 60 * 1000

    fun releaseTagFromLocation(location: String?): String? = location
        ?.let { runCatching { URI(it).path }.getOrNull() }
        ?.substringAfterLast("/tag/", "")
        ?.takeIf { it.isNotBlank() && '/' !in it }

    fun isStale(lastUpdateAt: Long, now: Long): Boolean =
        lastUpdateAt <= 0L || now - lastUpdateAt >= DAY_MS

    fun shouldUpdateForAnalysis(category: AnalysisErrorCategory, lastUpdateAt: Long, now: Long): Boolean =
        category in setOf(
            AnalysisErrorCategory.EXTRACTOR,
            AnalysisErrorCategory.UNSUPPORTED,
            AnalysisErrorCategory.PARSE
        ) && isStale(lastUpdateAt, now)

    fun canAutoRetry(lastAttemptAt: Long, now: Long): Boolean = lastAttemptAt <= 0L || now - lastAttemptAt >= RETRY_MS

    fun displayError(error: Throwable): String {
        val message = generateSequence(error) { it.cause }.joinToString(" ") { it.message.orEmpty() }
        return if (Regex("403|429|rate.?limit", RegexOption.IGNORE_CASE).containsMatchIn(message))
            "Motor güncellemesi şu an yapılamadı, sonra tekrar denenecek."
        else error.localizedMessage ?: "Güncelleme başarısız."
    }
}

object DownloadRecoveryPolicy {
    enum class Step { ARIA2C, LOCAL, UPDATE_ENGINE }

    fun isHttp403(message: String?): Boolean = message?.contains("HTTP Error 403", ignoreCase = true) == true

    fun isYoutubeUrl(url: String): Boolean = runCatching {
        val host = URI(url).host?.lowercase()?.removePrefix("www.") ?: return@runCatching false
        host == "youtube.com" || host.endsWith(".youtube.com") || host == "youtu.be"
    }.getOrDefault(false)

    fun steps(isYoutube: Boolean, initialHttp403: Boolean): List<Step> = when {
        !initialHttp403 -> if (isYoutube) listOf(Step.LOCAL) else listOf(Step.ARIA2C)
        isYoutube -> listOf(Step.LOCAL, Step.UPDATE_ENGINE, Step.LOCAL)
        else -> listOf(Step.ARIA2C, Step.LOCAL, Step.UPDATE_ENGINE, Step.LOCAL)
    }
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
                        error = ExtractorUpdatePolicy.displayError(error)
                    )
                }
            )
    }
}
