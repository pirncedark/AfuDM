package com.afudm.afutube

import java.net.URI

/** URL and response-type classifier shared by both WebView capture channels. */
object MediaSniffer {
    enum class Kind(val label: String) { HLS("HLS"), DASH("DASH"), MP4("MP4") }
    data class Candidate(val url: String, val kind: Kind, val contentType: String = "", val size: Long = 0, val quality: String = "")

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
