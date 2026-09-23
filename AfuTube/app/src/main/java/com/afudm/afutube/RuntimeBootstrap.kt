package com.afudm.afutube

import android.content.Context
import com.afudm.afutube.runtime.MediaRuntime
import com.afudm.afutube.updater.ExtractorUpdater

object RuntimeBootstrap {
    suspend fun prepare(context: Context): MediaRuntime.RuntimeStatus {
        val appContext = context.applicationContext
        return MediaRuntime.prepare(appContext) {
            val result = ExtractorUpdater.checkAndUpdate(
                appContext,
                channel = ExtractorUpdater.selectedChannel(appContext),
                force = true
            )
            check(result.error.isBlank()) { result.error }
        }
    }
}
