package com.afudm.afutube.feature.home

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.afudm.afutube.core.diagnostics.AnalysisError
import com.afudm.afutube.core.diagnostics.AnalysisFailure
import com.afudm.afutube.core.diagnostics.LastAnalysisErrorStore
import com.afudm.afutube.core.extractor.MediaInfo
import com.afudm.afutube.extractor.ExtractorManager
import com.afudm.afutube.extractor.YtDlpExtractor
import com.afudm.afutube.updater.ExtractorUpdater
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

data class HomeState(
    val url: String = "",
    val isLoading: Boolean = false,
    val mediaInfo: MediaInfo? = null,
    val error: String = "",
    val analysisError: AnalysisError? = null
)

class HomeViewModel(context: Context) : ViewModel() {
    private val appContext = context.applicationContext
    private val _state = MutableStateFlow(HomeState())
    val state: StateFlow<HomeState> = _state
    private val extractor = ExtractorManager.getInstance(appContext)
    private var analysisJob: Job? = null
    private var analysisSequence = 0L

    fun onUrlChange(url: String) {
        analysisJob?.cancel()
        analysisSequence++
        _state.value = _state.value.copy(url = url, error = "", analysisError = null, mediaInfo = null)
    }

    fun analyzeUrl(url: String) {
        if (url.isBlank()) return
        analysisJob?.cancel()
        val sequence = ++analysisSequence
        analysisJob = viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = "", analysisError = null, mediaInfo = null)
            val normalizedUrl = url.trim()
            val firstResult = extractor.extract(normalizedUrl)
            val result = retryAfterExtractorUpdateIfEligible(normalizedUrl, firstResult)
            if (sequence != analysisSequence) return@launch
            _state.value = if (result.isSuccess) {
                _state.value.copy(isLoading = false, mediaInfo = result.getOrNull())
            } else {
                val analysisError = result.exceptionOrNull()?.let { exception ->
                    when (exception) {
                        is YtDlpExtractor.AnalysisException -> exception.analysisError
                        else -> AnalysisFailure(
                            message = exception.localizedMessage ?: "Analiz başarısız",
                            traceback = exception.stackTraceToString()
                        ).toAnalysisError("bilinmiyor")
                    }
                }
                analysisError?.let(LastAnalysisErrorStore::set)
                _state.value.copy(
                    isLoading = false,
                    error = "YouTube videosu analiz edilemedi.",
                    analysisError = analysisError
                )
            }
        }
    }

    fun consumeMediaInfo(mediaInfo: MediaInfo) {
        if (_state.value.mediaInfo == mediaInfo) {
            _state.value = _state.value.copy(mediaInfo = null)
        }
    }

    private suspend fun retryAfterExtractorUpdateIfEligible(
        url: String,
        firstResult: Result<MediaInfo>
    ): Result<MediaInfo> {
        val exception = firstResult.exceptionOrNull() ?: return firstResult
        val analysisError = (exception as? YtDlpExtractor.AnalysisException)?.analysisError
            ?: return firstResult
        if (!ExtractorUpdater.shouldUpdateForAnalysis(appContext, analysisError.category, System.currentTimeMillis())) {
            return firstResult
        }

        val update = ExtractorUpdater.checkAndUpdate(
            context = appContext,
            channel = ExtractorUpdater.selectedChannel(appContext),
            force = false
        )
        return if (update.error.isBlank()) extractor.extract(url) else firstResult
    }
}
