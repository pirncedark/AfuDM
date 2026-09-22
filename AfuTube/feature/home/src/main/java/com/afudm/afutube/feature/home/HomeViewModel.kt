package com.afudm.afutube.feature.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.afudm.afutube.core.extractor.MediaInfo
import com.afudm.afutube.extractor.ExtractorManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class HomeState(
    val url       : String    = "",
    val isLoading : Boolean   = false,
    val mediaInfo : MediaInfo? = null,
    val error     : String    = ""
)

class HomeViewModel : ViewModel() {

    private val _state = MutableStateFlow(HomeState())
    val state: StateFlow<HomeState> = _state

    private val extractor = ExtractorManager.getInstance()

    fun onUrlChange(url: String) {
        _state.value = _state.value.copy(url = url, error = "", mediaInfo = null)
    }

    fun analyzeUrl(url: String) {
        if (url.isBlank()) return
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true, error = "", mediaInfo = null)
            val result = extractor.extract(url.trim())
            _state.value = if (result.isSuccess) {
                _state.value.copy(isLoading = false, mediaInfo = result.getOrNull())
            } else {
                _state.value.copy(
                    isLoading = false,
                    error = result.exceptionOrNull()?.localizedMessage ?: "Analiz başarısız"
                )
            }
        }
    }
}
