package com.afudm.afutube.core.extractor

import java.net.URI
import java.net.URLDecoder
import java.nio.charset.StandardCharsets
import kotlin.io.encoding.Base64

object UrlNormalizer {
    private val youtubeHosts = setOf("youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be")
    private val trackingQueryKeys = setOf("si")
    private val keptYoutubeQueryKeys = setOf("v", "list", "index", "t", "start")

    fun normalize(raw: String): String? {
        val trimmed = raw.trim()
        if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) return null

        return runCatching {
            val uri = URI(trimmed)
            val host = uri.host?.lowercase()?.removePrefix("www.") ?: return@runCatching trimmed
            val query = parseQuery(uri.rawQuery)
            if (host == "instagram.com") {
                val encoded = Regex("^/s/([^/]+)/?$").matchEntire(uri.path.orEmpty())?.groupValues?.get(1)
                val highlight = encoded?.let {
                    runCatching {
                        val padded = it.replace('-', '+').replace('_', '/').let { token ->
                            token.padEnd((token.length + 3) / 4 * 4, '=')
                        }
                        Base64.Default.decode(padded).toString(Charsets.UTF_8)
                    }.getOrNull()
                }?.let { Regex("highlight:([0-9]+)").matchEntire(it)?.groupValues?.get(1) }
                if (highlight != null) {
                    val story = query.firstOrNull { it.first == "story_media_id" }?.second
                    return@runCatching "https://www.instagram.com/stories/highlights/$highlight/" +
                        (story?.let { "?story_media_id=$it" } ?: "")
                }
            }
            if (host !in youtubeHosts) {
                val cleaned = uri.rawQuery.orEmpty().split('&').filter { part ->
                    if (part.isBlank()) return@filter false
                    val key = URLDecoder.decode(part.substringBefore('='), StandardCharsets.UTF_8.name()).lowercase()
                    !key.startsWith("utm_") && key != "si"
                }
                val builder = StringBuilder().append(uri.scheme).append("://").append(uri.rawAuthority).append(uri.rawPath.orEmpty())
                if (cleaned.isNotEmpty()) builder.append('?').append(cleaned.joinToString("&"))
                uri.rawFragment?.let { builder.append('#').append(it) }
                return@runCatching builder.toString()
            }
            val pathSegments = uri.rawPath.orEmpty().split('/').filter { it.isNotBlank() }
            val videoId = when {
                host == "youtu.be" -> pathSegments.firstOrNull()
                pathSegments.firstOrNull()?.equals("shorts", ignoreCase = true) == true -> pathSegments.getOrNull(1)
                else -> query.firstOrNull { it.first == "v" }?.second
            } ?: return@runCatching trimmed

            val kept = buildList {
                add("v=${videoId}")
                query.filter { (key, _) -> key in keptYoutubeQueryKeys && key != "v" }.forEach { (key, value) ->
                    add(if (value == null) key else "$key=$value")
                }
            }
            "https://www.youtube.com/watch?${kept.joinToString("&")}"
        }.getOrNull()
    }

    private fun parseQuery(rawQuery: String?): List<Pair<String, String?>> = rawQuery.orEmpty()
        .split('&')
        .filter { it.isNotBlank() }
        .mapNotNull { part ->
            val separator = part.indexOf('=')
            val rawKey = if (separator < 0) part else part.substring(0, separator)
            val rawValue = if (separator < 0) null else part.substring(separator + 1)
            val key = URLDecoder.decode(rawKey, StandardCharsets.UTF_8.name()).lowercase()
            if (key in trackingQueryKeys || key.startsWith("utm_")) null
            else key to rawValue
        }
}
