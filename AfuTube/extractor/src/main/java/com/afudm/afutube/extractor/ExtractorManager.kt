package com.afudm.afutube.extractor

import android.content.Context
import com.afudm.afutube.core.extractor.MediaExtractor
import com.afudm.afutube.core.extractor.MediaInfo
import com.afudm.afutube.core.extractor.UrlClassifier
import com.afudm.afutube.core.extractor.UrlNormalizer
import com.afudm.afutube.core.extractor.UrlType

/**
 * Merkezi extractor yöneticisi.
 * Uygulamanın geri kalanı yalnızca bu sınıfı kullanır —
 * hangi extractor'ın devreye girdiğini bilmez.
 *
 * Yeni bir extractor eklemek:
 *   1. MediaExtractor'ı implement et
 *   2. Buraya register() ile kaydet
 */
class ExtractorManager private constructor(context: Context) {

    private val extractors: MutableList<MediaExtractor> = mutableListOf()

    init {
        // Sıralı deneme — önce yt-dlp, fallback olarak DirectUrl
        register(YtDlpExtractor(context.applicationContext))
        register(DirectUrlExtractor())
    }

    fun register(extractor: MediaExtractor) {
        extractors.add(extractor)
    }

    suspend fun extract(url: String): Result<MediaInfo> {
        val normalizedUrl = UrlNormalizer.normalize(url) ?: url.trim()
        if (!UrlClassifier.isValid(normalizedUrl)) {
            return Result.failure(IllegalArgumentException("Geçersiz URL: $normalizedUrl"))
        }

        for (extractor in extractors) {
            if (extractor.supports(normalizedUrl)) {
                return runCatching { extractor.extract(normalizedUrl) }
            }
        }
        return Result.failure(UnsupportedOperationException("Bu URL için extractor bulunamadı"))
    }

    companion object {
        @Volatile private var INSTANCE: ExtractorManager? = null

        fun getInstance(context: Context): ExtractorManager =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: ExtractorManager(context.applicationContext).also { INSTANCE = it }
            }
    }
}
