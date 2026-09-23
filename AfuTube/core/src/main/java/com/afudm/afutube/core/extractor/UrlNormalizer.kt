package com.afudm.afutube.core.extractor

import java.net.URI
import java.net.URLDecoder
import java.nio.charset.StandardCharsets

object UrlNormalizer {
    private val youtubeHosts = setOf("youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be")
    private val keptQueryKeys = setOf("v", "list", "index", "t", "start")
    private val trackingQueryKeys = setOf("si", "feature", "pp")

    fun normalize(raw: String): String? {
        val trimmed = raw.trim()
        if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) return null

        return runCatching {
            val uri = URI(trimmed)
            val host = uri.host?.lowercase()?.removePrefix("www.") ?: return@runCatching trimmed
            if (host !in youtubeHosts) return@runCatching trimmed

            val query = parseQuery(uri.rawQuery)
            val pathSegments = uri.rawPath.orEmpty().split('/').filter { it.isNotBlank() }
            val videoId = when {
                host == "youtu.be" -> pathSegments.firstOrNull()
                pathSegments.firstOrNull()?.equals("shorts", ignoreCase = true) == true -> pathSegments.getOrNull(1)
                else -> query.firstOrNull { it.first == "v" }?.second
            } ?: return@runCatching trimmed

            val kept = buildList {
                add("v=${videoId}")
                query.filter { (key, _) -> key in keptQueryKeys && key != "v" }.forEach { (key, value) ->
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
