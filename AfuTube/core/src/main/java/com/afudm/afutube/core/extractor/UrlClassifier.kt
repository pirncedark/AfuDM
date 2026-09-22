package com.afudm.afutube.core.extractor

import java.net.URI

/**
 * URL'yi analiz ederek hangi extractor'ın kullanılacağına karar verir.
 * Uygulamanın diğer tarafları yalnızca bu sınıfı bilir.
 */
object UrlClassifier {

    private val YOUTUBE_HOSTS = setOf(
        "youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com",
        "music.youtube.com"
    )
    private val INSTAGRAM_HOSTS = setOf("instagram.com", "www.instagram.com")
    private val TWITTER_HOSTS   = setOf("twitter.com", "x.com", "www.twitter.com", "t.co")
    private val TIKTOK_HOSTS    = setOf("tiktok.com", "www.tiktok.com", "vm.tiktok.com")
    private val FACEBOOK_HOSTS  = setOf("facebook.com", "www.facebook.com", "fb.watch")

    private val DIRECT_VIDEO_EXT = setOf("mp4", "mkv", "webm", "avi", "mov", "flv", "m2ts")
    private val DIRECT_AUDIO_EXT = setOf("mp3", "m4a", "aac", "flac", "opus", "ogg", "wav")

    fun classify(url: String): UrlType {
        val trimmed = url.trim()
        return try {
            val uri  = URI(trimmed)
            val host = uri.host?.removePrefix("www.")?.lowercase() ?: return UrlType.UNSUPPORTED
            val path = uri.path?.lowercase() ?: ""

            when {
                host in YOUTUBE_HOSTS    -> UrlType.YOUTUBE
                host in INSTAGRAM_HOSTS  -> UrlType.INSTAGRAM
                host in TWITTER_HOSTS    -> UrlType.TWITTER_X
                host in TIKTOK_HOSTS     -> UrlType.TIKTOK
                host in FACEBOOK_HOSTS   -> UrlType.FACEBOOK
                path.endsWith(".m3u8")   -> UrlType.HLS_M3U8
                path.endsWith(".mpd")    -> UrlType.DASH_MPD
                DIRECT_VIDEO_EXT.any { path.endsWith(".$it") } -> UrlType.DIRECT_VIDEO
                DIRECT_AUDIO_EXT.any { path.endsWith(".$it") } -> UrlType.DIRECT_AUDIO
                else                     -> UrlType.YOUTUBE // yt-dlp 1800+ site destekler — try it
            }
        } catch (_: Exception) {
            UrlType.UNSUPPORTED
        }
    }

    fun isValid(url: String): Boolean =
        classify(url) != UrlType.UNSUPPORTED &&
        (url.startsWith("http://") || url.startsWith("https://"))
}
