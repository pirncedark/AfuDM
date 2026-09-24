package com.afudm.afutube

import android.content.Intent
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class ShareIntentEvent(val sequence: Long, val url: String?)
data class ShareIntentPayload(
    val action: String? = null,
    val text: String? = null,
    val subject: String? = null,
    val data: String? = null
)

object ShareUrlExtractor {
    private val urlPattern = Regex("https?://[^\\s<>\\\"']+")
    private val trailingPunctuation = Regex("[.,!?;:)}\\]]+$")

    fun firstHttpUrl(intent: Intent?): String? {
        return firstHttpUrl(
            ShareIntentPayload(
                action = intent?.action,
                text = intent?.getStringExtra(Intent.EXTRA_TEXT),
                subject = intent?.getStringExtra(Intent.EXTRA_SUBJECT),
                data = intent?.data?.toString()
            )
        )
    }

    fun firstHttpUrl(payload: ShareIntentPayload): String? {
        val candidates = listOfNotNull(payload.text, payload.subject, payload.data)
        return candidates.asSequence()
            .flatMap { value -> urlPattern.findAll(value).map { it.value } }
            .map { it.replace(trailingPunctuation, "") }
            .firstOrNull()
    }
}

class ShareIntentViewModel : ViewModel() {
    private val _events = MutableStateFlow<ShareIntentEvent?>(null)
    val events: StateFlow<ShareIntentEvent?> = _events.asStateFlow()
    private var sequence = 0L
    private var consumedSequence = 0L

    fun publish(intent: Intent?) {
        publishUrl(ShareUrlExtractor.firstHttpUrl(intent))
    }

    fun publish(payload: ShareIntentPayload) {
        publishUrl(ShareUrlExtractor.firstHttpUrl(payload))
    }

    fun consume(sequence: Long): ShareIntentEvent? {
        val event = _events.value ?: return null
        if (event.sequence != sequence || consumedSequence >= sequence) return null
        consumedSequence = sequence
        return event
    }

    private fun publishUrl(url: String?) {
        sequence += 1
        _events.value = ShareIntentEvent(sequence, url)
    }
}
