package com.afudm.afutube

import android.app.Application
import com.afudm.afutube.runtime.MediaRuntime

class AfuTubeApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        MediaRuntime.start(this)
    }
}
