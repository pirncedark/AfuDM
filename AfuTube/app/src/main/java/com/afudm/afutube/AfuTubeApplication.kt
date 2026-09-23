package com.afudm.afutube

import android.app.Application
import com.afudm.afutube.runtime.MediaRuntime
import com.afudm.afutube.runtime.MediaRuntimeHealthChecker
import com.afudm.afutube.updater.ExtractorUpdater
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class AfuTubeApplication : Application() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    // Motor hazirliginin TEK sahibi burasi; Compose yalnizca MediaRuntime.status'u izler.
    override fun onCreate() {
        super.onCreate()
        scope.launch {
            val status = RuntimeBootstrap.prepare(this@AfuTubeApplication)
            if (status.state != MediaRuntime.RuntimeState.READY) return@launch
            // Ana ekran acildiktan sonra arka planda: surum eski/bilinmiyorsa zorla, degilse politikaya gore guncelle.
            runCatching {
                val version = ExtractorUpdater.currentVersion(this@AfuTubeApplication)
                if (MediaRuntimeHealthChecker.check(version).requiresExtractorUpdate) {
                    ExtractorUpdater.checkAndUpdate(this@AfuTubeApplication, force = true)
                } else {
                    ExtractorUpdater.maybeAutoUpdate(this@AfuTubeApplication)
                }
            }
        }
    }
}
