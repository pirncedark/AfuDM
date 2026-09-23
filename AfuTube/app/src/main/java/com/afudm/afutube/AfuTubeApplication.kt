package com.afudm.afutube

import android.app.Application
import com.afudm.afutube.runtime.MediaRuntime
import com.afudm.afutube.updater.ExtractorUpdater
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class AfuTubeApplication : Application() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        MediaRuntime.start(this)
        scope.launch {
            runCatching {
                MediaRuntime.ensureInitialized(this@AfuTubeApplication)
                ExtractorUpdater.maybeAutoUpdate(this@AfuTubeApplication)
            }
        }
    }
}
