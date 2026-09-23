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
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class HomeState(
    val url: String = "",
    val isLoading: Boolean = false,
    val mediaInfo: MediaInfo? = null,
    val error: String = "",
    val analysisError: AnalysisError? = null
)

class HomeViewModel(context: Context) : ViewModel() {
    private val _state = MutableStateFlow(HomeState())
    val state: StateFlow<HomeState> = _state
    private val extractor = ExtractorManager.getInstance(context.applicationContext)

    fun onUrlChange(url: String) {
        _state.value = _state.value.copy(url = url, error = "", analysisError = null, mediaInfo = null)
    }

    fun analyzeUrl(url: String) {
        if (url.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = "", analysisError = null, mediaInfo = null)
            val result = extractor.extract(url.trim())
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
}
