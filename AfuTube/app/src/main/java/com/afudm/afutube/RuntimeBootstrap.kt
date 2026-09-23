package com.afudm.afutube

import android.content.Context
import com.afudm.afutube.runtime.MediaRuntime

object RuntimeBootstrap {
    suspend fun prepare(context: Context): MediaRuntime.RuntimeStatus =
        MediaRuntime.prepare(context.applicationContext)
}
