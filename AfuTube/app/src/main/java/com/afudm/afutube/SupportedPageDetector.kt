package com.afudm.afutube

import java.net.URI

/** Recognizes page URLs supported by yt-dlp for the browser's direct page action. */
object SupportedPageDetector {
    fun supports(rawUrl: String): Boolean {
        val uri = runCatching { URI(rawUrl) }.getOrNull() ?: return false
        if (!uri.scheme.equals("http", true) && !uri.scheme.equals("https", true)) return false
        val host = uri.host?.lowercase()?.removePrefix("www.") ?: return false
        val path = uri.path.orEmpty()
        return when {
            host == "youtube.com" || host == "m.youtube.com" || host == "music.youtube.com" ->
                path == "/watch" || path.startsWith("/shorts/")
            host == "youtu.be" -> path.trim('/').isNotEmpty()
            host == "instagram.com" -> path.matches(Regex("^/(p|reel)/[^/]+/?$"))
            host == "tiktok.com" -> path.matches(Regex("^/@[^/]+/video/\\d+/?$"))
            host == "x.com" || host == "twitter.com" -> path.matches(Regex("^/[^/]+/status/\\d+/?$"))
            host == "facebook.com" || host == "m.facebook.com" || host == "www.facebook.com" ->
                path.matches(Regex("^/[^/]+/videos/[^/]+/?$")) || path == "/watch" || path.matches(Regex("^/reel/[^/]+/?$"))
            host == "vimeo.com" -> path.matches(Regex("^/\\d+/?$"))
            host == "dailymotion.com" -> path.matches(Regex("^/video/[^/?]+/?$"))
            else -> false
        }
    }
}
