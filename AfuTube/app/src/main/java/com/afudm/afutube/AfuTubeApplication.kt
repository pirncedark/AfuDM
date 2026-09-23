package com.afudm.afutube

import android.app.Application
import com.afudm.afutube.updater.ExtractorUpdater
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class AfuTubeApplication : Application() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        scope.launch {
            val status = RuntimeBootstrap.prepare(this@AfuTubeApplication)
            if (status.state == com.afudm.afutube.runtime.MediaRuntime.RuntimeState.READY) {
                ExtractorUpdater.maybeAutoUpdate(this@AfuTubeApplication)
            }
        }
    }
}
