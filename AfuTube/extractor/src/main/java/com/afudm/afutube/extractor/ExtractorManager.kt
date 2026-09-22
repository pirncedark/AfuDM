package com.afudm.afutube.extractor

import android.content.Context
import com.afudm.afutube.core.extractor.MediaExtractor
import com.afudm.afutube.core.extractor.MediaInfo
import com.afudm.afutube.core.extractor.UrlClassifier
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
        if (!UrlClassifier.isValid(url)) {
            return Result.failure(IllegalArgumentException("Geçersiz URL: $url"))
        }

        for (extractor in extractors) {
            if (extractor.supports(url)) {
                return runCatching { extractor.extract(url) }
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
