package com.afudm.afutube.extractor

import com.afudm.afutube.core.extractor.MediaExtractor
import com.afudm.afutube.core.extractor.MediaFormat
import com.afudm.afutube.core.extractor.MediaInfo
import com.afudm.afutube.core.extractor.UrlClassifier
import com.afudm.afutube.core.extractor.UrlType
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

/**
 * Doğrudan indirilebilir URL'ler için fallback extractor.
 * HEAD isteği atarak dosya boyutu ve tipini alır.
 */
class DirectUrlExtractor : MediaExtractor {

    override suspend fun supports(url: String): Boolean {
        val type = UrlClassifier.classify(url)
        return type == UrlType.DIRECT_VIDEO || type == UrlType.DIRECT_AUDIO
    }

    override suspend fun extract(url: String): MediaInfo = withContext(Dispatchers.IO) {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod   = "HEAD"
            connectTimeout  = 10_000
            readTimeout     = 10_000
            instanceFollowRedirects = true
        }
        conn.connect()

        val contentType = conn.contentType ?: "application/octet-stream"
        val contentLen  = conn.contentLengthLong.coerceAtLeast(0)
        val finalUrl    = conn.url.toString()
        val ext         = finalUrl.substringAfterLast('.').substringBefore('?').take(5)
        val isAudio     = contentType.startsWith("audio")

        MediaInfo(
            id        = finalUrl.hashCode().toString(),
            title     = finalUrl.substringAfterLast('/').substringBefore('?').ifBlank { "Media" },
            thumbnail = "",
            uploader  = URL(finalUrl).host,
            duration  = 0,
            sourceUrl = finalUrl,
            formats   = listOf(
                MediaFormat(
                    formatId   = "direct",
                    ext        = ext.ifBlank { if (isAudio) "mp3" else "mp4" },
                    quality    = if (isAudio) "audio-only" else "direct",
                    resolution = "",
                    fps        = 0,
                    vcodec     = if (isAudio) "none" else "unknown",
                    acodec     = if (isAudio) "unknown" else "unknown",
                    fileSizeB  = contentLen,
                    url        = finalUrl
                )
            )
        )
    }
}
