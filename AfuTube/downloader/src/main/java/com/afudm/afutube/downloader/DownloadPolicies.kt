package com.afudm.afutube.downloader

/** Pure policies shared by workers and JVM tests. */
object DownloadPolicies {
    const val MAX_HTTP_ATTEMPTS = 3

    enum class Action { PAUSE, RESUME, RETRY, NONE }

    fun actionForState(state: String): Action = when (state) {
        "RUNNING" -> Action.PAUSE
        "CANCELLED" -> Action.RESUME
        "FAILED" -> Action.RETRY
        else -> Action.NONE
    }

    fun isRateLimitedOrForbidden(message: String): Boolean {
        val text = message.lowercase()
        return Regex("(^|\\D)(403|429)(\\D|$)").containsMatchIn(text) ||
            "forbidden" in text || "too many requests" in text
    }

    fun shouldRetry(message: String, attempt: Int): Boolean =
        attempt < MAX_HTTP_ATTEMPTS - 1 && isRateLimitedOrForbidden(message)

    fun shouldRetryFailure(message: String?, attempt: Int, cancelled: Boolean): Boolean =
        !cancelled && !message.isNullOrBlank() && shouldRetry(message, attempt)

    fun retryDelayMillis(retryNumber: Int): Long =
        1_000L shl retryNumber.coerceIn(0, MAX_HTTP_ATTEMPTS - 2)

    fun parseRateLimitKbps(value: String): Int = value.toIntOrNull()?.coerceAtLeast(0) ?: 0

    fun ytDlpOptions(audioFormat: String, embedThumbnail: Boolean, embedChapters: Boolean, rateLimitKbps: Int): List<Pair<String, String?>> = buildList {
        add("--continue" to null)
        if (audioFormat.isNotBlank()) {
            add("--extract-audio" to null)
            add("--audio-format" to audioFormat)
        }
        if (embedThumbnail) add("--embed-thumbnail" to null)
        if (embedChapters) add("--embed-chapters" to null)
        if (rateLimitKbps > 0) add("--limit-rate" to "${rateLimitKbps}K")
    }

    fun extractHttpLinks(text: String): List<String> {
        val pattern = Regex("https?://[^\\s<>\\\"']+", RegexOption.IGNORE_CASE)
        val punctuation = Regex("[.,!?;:)}\\]]+$")
        return pattern.findAll(text).map { it.value.replace(punctuation, "") }.distinct().toList()
    }
}
