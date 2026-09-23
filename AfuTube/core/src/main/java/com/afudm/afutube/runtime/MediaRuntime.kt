package com.afudm.afutube.runtime

import android.content.Context
import android.util.Log
import com.yausername.aria2c.Aria2c
import com.yausername.ffmpeg.FFmpeg
import com.yausername.youtubedl_android.YoutubeDL
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

object MediaRuntime {
    private const val TAG = "AfuTubeMediaRuntime"
    private const val FAILURE_MESSAGE = "Medya motoru kullanılamıyor."
    private const val USER_FAILURE_MESSAGE = "Medya motoru hazırlanamadı"

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val engineMutex = Mutex()
    private val prepareMutex = Mutex()
    private val _status = MutableStateFlow(RuntimeStatus())
    val status: StateFlow<RuntimeStatus> = _status.asStateFlow()

    private val coordinator = InitCoordinator<Context> { context ->
        YoutubeDL.getInstance().init(context)
        FFmpeg.getInstance().init(context)
        Aria2c.getInstance().init(context)
    }

    @Volatile
    private var initializationError: Throwable? = null

    fun start(context: Context) {
        scope.launch { runCatching { ensureInitialized(context.applicationContext) } }
    }

    suspend fun ensureInitialized(context: Context) = withContext(Dispatchers.IO) {
        try {
            _status.value = _status.value.copy(state = RuntimeState.INITIALIZING)
            coordinator.ensureInitialized(context.applicationContext)
        } catch (error: Throwable) {
            initializationError = error
            _status.value = RuntimeStatus(RuntimeState.FAILED, USER_FAILURE_MESSAGE, error.localizedMessage.orEmpty())
            Log.e(TAG, "Media runtime initialization failed", error)
            throw MediaInitializationException(FAILURE_MESSAGE, error)
        }
    }

    /**
     * Yalnizca yerel motoru (Python / yt-dlp / FFmpeg / aria2) hazirlar.
     * Ag / yt-dlp guncellemesi burada YOK: internet olmasa da uygulama acilir.
     * Guncelleme READY olduktan sonra arka planda yapilir (AfuTubeApplication).
     */
    suspend fun prepare(context: Context): RuntimeStatus = prepareMutex.withLock {
        if (_status.value.state == RuntimeState.READY) return@withLock _status.value
        _status.value = RuntimeStatus(RuntimeState.INITIALIZING)
        try {
            ensureInitialized(context.applicationContext)
            _status.value = RuntimeStatus(RuntimeState.READY, details = "Python / yt-dlp / FFmpeg / aria2 hazır.")
        } catch (error: Throwable) {
            initializationError = error
            _status.value = RuntimeStatus(
                RuntimeState.FAILED,
                USER_FAILURE_MESSAGE,
                error.localizedMessage ?: error.stackTraceToString()
            )
            Log.e(TAG, "Media runtime preparation failed", error)
        }
        _status.value
    }

    fun lastError(): Throwable? = initializationError

    suspend fun <T> withEngine(block: suspend () -> T): T = engineMutex.withLock { block() }

    enum class RuntimeState { IDLE, INITIALIZING, READY, FAILED }

    data class RuntimeStatus(
        val state: RuntimeState = RuntimeState.IDLE,
        val message: String = "",
        val details: String = ""
    )

    class MediaInitializationException(message: String, cause: Throwable) : RuntimeException(message, cause)
}
