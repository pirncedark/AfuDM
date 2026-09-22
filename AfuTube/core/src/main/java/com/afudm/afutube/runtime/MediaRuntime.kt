package com.afudm.afutube.runtime

import android.content.Context
import android.util.Log
import com.yausername.aria2c.Aria2c
import com.yausername.ffmpeg.FFmpeg
import com.yausername.youtubedl_android.YoutubeDL
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

object MediaRuntime {
    private const val TAG = "AfuTubeMediaRuntime"
    private const val FAILURE_MESSAGE = "Medya motoru başlatılamadı. Uygulamayı yeniden açıp tekrar deneyin."

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val coordinator = InitCoordinator<Context> { context ->
        YoutubeDL.getInstance().init(context)
        FFmpeg.getInstance().init(context)
        Aria2c.getInstance().init(context)
    }

    @Volatile
    private var initializationError: Throwable? = null

    fun start(context: Context) {
        val appContext = context.applicationContext
        scope.launch {
            runCatching { coordinator.ensureInitialized(appContext) }
                .onFailure { error ->
                    initializationError = error
                    Log.e(TAG, "Medya motoru başlatılamadı", error)
                }
        }
    }

    suspend fun ensureInitialized(context: Context) = withContext(Dispatchers.IO) {
        try {
            coordinator.ensureInitialized(context.applicationContext)
        } catch (error: Throwable) {
            initializationError = error
            Log.e(TAG, "Medya motoru kullanılamıyor", error)
            throw MediaInitializationException(FAILURE_MESSAGE, error)
        }
    }

    fun lastError(): Throwable? = initializationError

    class MediaInitializationException(message: String, cause: Throwable) : RuntimeException(message, cause)
}
