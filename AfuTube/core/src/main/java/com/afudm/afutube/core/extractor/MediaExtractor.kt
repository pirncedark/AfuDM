package com.afudm.afutube.core.extractor

/**
 * Tüm extractor'ların uygulaması gereken sözleşme.
 * Uygulamanın geri kalanı yt-dlp'nin ne olduğunu bilmez.
 */
interface MediaExtractor {
    /** Bu extractor verilen URL'yi destekliyor mu? */
    suspend fun supports(url: String): Boolean

    /** URL'yi analiz et, formatları çıkar. */
    suspend fun extract(url: String): MediaInfo
}

// ─── Veri modelleri ───────────────────────────────────────────────────────────

data class MediaInfo(
    val id        : String,
    val title     : String,
    val thumbnail : String,
    val uploader  : String,
    val duration  : Int,          // saniye
    val sourceUrl : String,
    val formats   : List<MediaFormat>
)

data class MediaFormat(
    val formatId   : String,
    val ext        : String,      // mp4, webm, m4a, mp3 …
    val quality    : String,      // 1080p, 720p, audio-only …
    val resolution : String,      // "1920x1080" ya da ""
    val fps        : Int,
    val vcodec     : String,      // "avc1.…" ya da "none"
    val acodec     : String,      // "mp4a.…" ya da "none"
    val fileSizeB  : Long,        // 0 = bilinmiyor
    val url        : String,
    val isAudioOnly: Boolean = vcodec == "none" || vcodec.isBlank()
) {
    val fileSizeMB: String get() =
        if (fileSizeB > 0) "%.1f MB".format(fileSizeB / 1_048_576f) else ""

    /** Kullanıcı arayüzünde gösterilecek etiket */
    val label: String get() = buildString {
        if (!isAudioOnly) {
            append(resolution.ifBlank { quality })
            if (fps > 0 && fps != 30) append(" ${fps}fps")
        } else {
            append("🎵 ${ext.uppercase()}")
            if (quality.isNotBlank()) append(" • $quality")
        }
        if (fileSizeMB.isNotBlank()) append("  •  $fileSizeMB")
    }
}

/** URL türünü sınıflandırır */
enum class UrlType {
    YOUTUBE, INSTAGRAM, TWITTER_X, TIKTOK, FACEBOOK,
    DIRECT_VIDEO, DIRECT_AUDIO, HLS_M3U8, DASH_MPD,
    UNSUPPORTED
}
