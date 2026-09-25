package com.afudm.afutube

import java.net.URI

/** URL and response-type classifier shared by both WebView capture channels. */
object MediaSniffer {
    enum class Kind(val label: String) { HLS("HLS"), DASH("DASH"), MP4("MP4") }
    data class Candidate(val url: String, val kind: Kind, val contentType: String = "", val size: Long = 0, val quality: String = "")

    private val adHosts = setOf(
        "doubleclick.net", "googlesyndication.com", "googleadservices.com", "googleads.g.doubleclick.net",
        "imasdk.googleapis.com", "pagead2.googlesyndication.com", "adservice.google.com", "g.doubleclick.net",
        "2mdn.net", "adnxs.com", "pubmatic.com", "springserve.com", "spotxchange.com", "teads.tv",
        "criteo.com", "rubiconproject.com", "taboola.com", "outbrain.com", "innovid.com", "serving-sys.com", "moatads.com"
    )
    private val adPathMarkers = listOf("/vast", "/vmap", "/ads/", "adtag", "ad_type", "preroll")

    fun isAdOrTrackingRequest(rawUrl: String): Boolean {
        val uri = runCatching { URI(rawUrl) }.getOrNull() ?: return false
        val host = uri.host?.lowercase()?.trimEnd('.') ?: return false
        val path = uri.rawPath.orEmpty().lowercase()
        return adHosts.any { host == it || host.endsWith(".$it") } || adPathMarkers.any(path::contains)
    }

    fun shouldIgnoreRequest(rawUrl: String, pageUrl: String): Boolean {
        if (isAdOrTrackingRequest(rawUrl)) return true
        val pageHost = runCatching { URI(pageUrl).host?.lowercase().orEmpty() }.getOrDefault("")
        if (!SupportedPageDetector.supports(pageUrl) || !isYoutubeHost(pageHost)) return false
        val requestHost = runCatching { URI(rawUrl).host?.lowercase().orEmpty() }.getOrDefault("")
        return requestHost == "googlevideo.com" || requestHost.endsWith(".googlevideo.com") || isYoutubeHost(requestHost)
    }

    fun rankCandidates(candidates: List<Candidate>, pageUrl: String): List<Candidate> {
        val pageDomain = approximateDomain(pageUrl)
        return candidates.sortedWith(
            compareByDescending<Candidate> { approximateDomain(it.url) == pageDomain }
                .thenByDescending { it.kind == Kind.HLS || it.kind == Kind.DASH }
                .thenByDescending { it.size }
        )
    }

    private fun approximateDomain(url: String): String = runCatching {
        URI(url).host.orEmpty().lowercase().removePrefix("www.").split('.').takeLast(2).joinToString(".")
    }.getOrDefault("")

    private fun isYoutubeHost(host: String): Boolean =
        host == "youtube.com" || host.endsWith(".youtube.com") || host == "youtu.be" || host.endsWith(".youtu.be")

    fun classify(rawUrl: String, contentType: String = ""): Kind? {
        if (!isHttpUrl(rawUrl)) return null
        val url = rawUrl.substringBefore('#').substringBefore('?').lowercase()
        val type = contentType.substringBefore(';').trim().lowercase()
        return when {
            url.endsWith(".m3u8") || type.contains("mpegurl") -> Kind.HLS
            url.endsWith(".mpd") || type.contains("dash+xml") -> Kind.DASH
            url.endsWith(".mp4") || url.endsWith(".webm") || url.endsWith(".m4v") || type in setOf("video/mp4", "video/webm", "video/x-m4v", "video/quicktime") -> Kind.MP4
            else -> null
        }
    }

    fun isHttpUrl(value: String): Boolean = value.length in 1..4096 && runCatching {
        val uri = URI(value)
        (uri.scheme.equals("http", true) || uri.scheme.equals("https", true)) && !uri.host.isNullOrBlank()
    }.getOrDefault(false)

    fun isSegment(url: String, hasRange: Boolean = false): Boolean {
        val path = runCatching { URI(url).path.lowercase() }.getOrDefault("")
        return hasRange || listOf(".ts", ".m4s", ".aac", ".vtt", ".key").any(path::endsWith)
    }

    fun masterQualities(body: String): List<String> = Regex("""#EXT-X-STREAM-INF:([^\r\n]*)[\r\n]+[^#\r\n][^\r\n]*""")
        .findAll(body.take(256 * 1024)).mapNotNull { match ->
            val attrs = match.groupValues[1]
            Regex("""RESOLUTION=\d+x(\d+)""").find(attrs)?.groupValues?.get(1)?.plus("p")
                ?: Regex("""BANDWIDTH=(\d+)""").find(attrs)?.groupValues?.get(1)?.toLongOrNull()?.let { "${it / 1000} kbps" }
        }.distinct().toList()

    fun masterVariants(body: String, masterUrl: String): Set<String> {
        if (!isHttpUrl(masterUrl)) return emptySet()
        val lines = body.take(256 * 1024).lineSequence().map(String::trim).toList()
        return lines.mapIndexedNotNull { index, line ->
            if (!line.startsWith("#EXT-X-STREAM-INF:") || index + 1 >= lines.size) return@mapIndexedNotNull null
            lines[index + 1].takeIf { it.isNotEmpty() && !it.startsWith("#") }?.let { runCatching { URI(masterUrl).resolve(it).toString() }.getOrNull() }
        }.filter(::isHttpUrl).toSet()
    }
}
