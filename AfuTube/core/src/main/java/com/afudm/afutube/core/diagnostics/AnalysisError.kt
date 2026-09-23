package com.afudm.afutube.core.diagnostics

import java.util.Locale

enum class AnalysisErrorCategory {
    EXTRACTOR, UNSUPPORTED, PARSE, ACCESS_403, NETWORK_TIMEOUT, OTHER
}

data class AnalysisError(
    val category: AnalysisErrorCategory,
    val message: String,
    val ytDlpVersion: String,
    val exitCode: Int?,
    val traceback: String
) {
    val categoryLabel: String
        get() = when (category) {
            AnalysisErrorCategory.EXTRACTOR -> "Extractor hatası"
            AnalysisErrorCategory.UNSUPPORTED -> "Desteklenmeyen içerik"
            AnalysisErrorCategory.PARSE -> "Yanıt ayrıştırılamadı"
            AnalysisErrorCategory.ACCESS_403 -> "Erişim reddedildi (403)"
            AnalysisErrorCategory.NETWORK_TIMEOUT -> "Ağ bağlantısı / zaman aşımı"
            AnalysisErrorCategory.OTHER -> "Diğer"
        }

    fun copyText(): String = buildString {
        appendLine("AfuTube son analiz hatası")
        appendLine("Sınıf: $categoryLabel")
        appendLine("yt-dlp: $ytDlpVersion")
        appendLine("Exit code: ${exitCode ?: "yok"}")
        appendLine("Mesaj: $message")
        appendLine("Traceback:")
        append(traceback)
    }
}

data class AnalysisFailure(
    val message: String,
    val exitCode: Int? = null,
    val traceback: String = message
) {
    fun toAnalysisError(ytDlpVersion: String): AnalysisError {
        val text = "$message\n$traceback".lowercase(Locale.ROOT)
        val category = when {
            "403" in text || "forbidden" in text -> AnalysisErrorCategory.ACCESS_403
            "timeout" in text || "timed out" in text || "network is unreachable" in text ||
                "unable to resolve host" in text || "connection reset" in text -> AnalysisErrorCategory.NETWORK_TIMEOUT
            "unsupported" in text || "not available" in text || "does not support" in text -> AnalysisErrorCategory.UNSUPPORTED
            "parse" in text || "json" in text || "traceback" in text -> AnalysisErrorCategory.PARSE
            "extractor" in text || "youtube" in text || "yt-dlp" in text -> AnalysisErrorCategory.EXTRACTOR
            else -> AnalysisErrorCategory.OTHER
        }
        return AnalysisError(
            category = category,
            message = message.ifBlank { "Video analiz edilemedi." },
            ytDlpVersion = ytDlpVersion,
            exitCode = exitCode,
            traceback = SensitiveDataRedactor.redact(traceback)
        )
    }
}

object LastAnalysisErrorStore {
    @Volatile private var latest: AnalysisError? = null
    fun set(error: AnalysisError) { latest = error.copy(traceback = SensitiveDataRedactor.redact(error.traceback)) }
    fun get(): AnalysisError? = latest
}
