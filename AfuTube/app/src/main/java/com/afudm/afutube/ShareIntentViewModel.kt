package com.afudm.afutube

import android.content.Intent
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class ShareIntentEvent(val sequence: Long, val urls: List<String>) { val url: String get() = urls.first() }
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
        return allHttpUrls(payload).firstOrNull()
    }

    fun allHttpUrls(payload: ShareIntentPayload): List<String> {
        val candidates = listOfNotNull(payload.text, payload.subject, payload.data)
        return candidates.asSequence()
            .flatMap { value -> urlPattern.findAll(value).map { it.value } }
            .map { it.replace(trailingPunctuation, "") }
            .distinct()
            .toList()
    }
}

class ShareIntentViewModel : ViewModel() {
    private val _events = MutableStateFlow<ShareIntentEvent?>(null)
    val events: StateFlow<ShareIntentEvent?> = _events.asStateFlow()
    private var sequence = 0L

    fun publish(intent: Intent?) {
        if (intent == null) return
        publishUrls(ShareUrlExtractor.allHttpUrls(ShareIntentPayload(
            action = intent.action,
            text = intent.getStringExtra(Intent.EXTRA_TEXT),
            subject = intent.getStringExtra(Intent.EXTRA_SUBJECT),
            data = intent.data?.toString()
        )))
    }

    fun publish(payload: ShareIntentPayload) {
        publishUrls(ShareUrlExtractor.allHttpUrls(payload))
    }

    private fun publishUrls(urls: List<String>) {
        if (urls.isEmpty()) return
        sequence += 1
        _events.value = ShareIntentEvent(sequence, urls)
    }
}
