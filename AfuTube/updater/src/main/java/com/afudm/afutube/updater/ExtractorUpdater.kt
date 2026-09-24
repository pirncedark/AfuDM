package com.afudm.afutube.updater

import android.content.Context
import com.afudm.afutube.core.diagnostics.AnalysisErrorCategory
import com.afudm.afutube.runtime.MediaRuntime
import com.yausername.youtubedl_android.YoutubeDL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

object ExtractorUpdater {
    enum class Channel { STABLE, NIGHTLY }

    private const val PREFS = "afutube_extractor"
    private const val AUTO_UPDATE = "auto_update"
    private const val CHANNEL = "channel"
    private const val LAST_UPDATE = "last_update"
    private const val LAST_ATTEMPT = "last_attempt"

    private val coordinator = ExtractorUpdateCoordinator<Context>(
        version = { context ->
            MediaRuntime.withEngine {
                MediaRuntime.ensureInitialized(context)
                YoutubeDL.getInstance().version(context) ?: "bilinmiyor"
            }
        },
        update = { context, channel ->
            MediaRuntime.withEngine {
                YoutubeDL.getInstance().updateYoutubeDL(context, channel)
            }
        }
    )

    fun libraryChannel(channel: Channel): YoutubeDL.UpdateChannel = when (channel) {
        Channel.STABLE -> YoutubeDL.UpdateChannel.STABLE
        Channel.NIGHTLY -> YoutubeDL.UpdateChannel.NIGHTLY
    }

    suspend fun currentVersion(context: Context): String = withContext(Dispatchers.IO) {
        runCatching {
            MediaRuntime.withEngine {
                MediaRuntime.ensureInitialized(context.applicationContext)
                YoutubeDL.getInstance().version(context) ?: "bilinmiyor"
            }
        }.getOrElse { "hata: ${it.localizedMessage ?: "bilinmiyor"}" }
    }

    suspend fun checkAndUpdate(
        context: Context,
        channel: Channel = selectedChannel(context),
        force: Boolean = false,
        now: Long = System.currentTimeMillis()
    ): ExtractorUpdateResult = withContext(Dispatchers.IO) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val lastUpdate = prefs.getLong(LAST_UPDATE, 0L)
        if (!force && !ExtractorUpdatePolicy.isStale(lastUpdate, now)) {
            val current = currentVersion(context)
            return@withContext ExtractorUpdateResult(
                updated = false,
                oldVersion = current,
                newVersion = current,
                attempted = false
            )
        }

        val result = coordinator.update(context.applicationContext, channel, force = force, now = now)
        if (result.attempted) prefs.edit().putLong(LAST_ATTEMPT, now).apply()
        if (result.attempted && result.error.isBlank()) {
            prefs.edit()
                .putLong(LAST_UPDATE, now)
                .putString(CHANNEL, channel.name)
                .apply()
        }
        result
    }

    suspend fun maybeAutoUpdate(context: Context, now: Long = System.currentTimeMillis()): ExtractorUpdateResult? {
        if (!autoUpdateEnabled(context)) return null
        val lastAttempt = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(LAST_ATTEMPT, 0L)
        if (!ExtractorUpdatePolicy.canAutoRetry(lastAttempt, now)) return null
        return checkAndUpdate(context, selectedChannel(context), force = false, now = now)
    }

    fun shouldUpdateForAnalysis(context: Context, category: AnalysisErrorCategory, now: Long): Boolean {
        val lastUpdate = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(LAST_UPDATE, 0L)
        return ExtractorUpdatePolicy.shouldUpdateForAnalysis(category, lastUpdate, now)
    }

    fun lastUpdateAt(context: Context): Long =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(LAST_UPDATE, 0L)

    fun autoUpdateEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(AUTO_UPDATE, true)

    fun setAutoUpdateEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(AUTO_UPDATE, enabled).apply()
    }

    fun selectedChannel(context: Context): Channel =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(CHANNEL, Channel.STABLE.name)
            ?.let { runCatching { Channel.valueOf(it) }.getOrNull() }
            ?: Channel.STABLE

    fun setSelectedChannel(context: Context, channel: Channel) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(CHANNEL, channel.name).apply()
    }
}
