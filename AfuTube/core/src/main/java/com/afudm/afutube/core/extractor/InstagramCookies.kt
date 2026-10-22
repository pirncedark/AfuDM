package com.afudm.afutube.core.extractor

import android.content.Context
import android.webkit.CookieManager
import java.io.File
import java.net.URI
import java.net.URLDecoder

object InstagramCookies {
    fun toNetscape(cookieHeader: String, domain: String = ".instagram.com"): String = buildString {
        appendLine("# Netscape HTTP Cookie File")
        cookieHeader.split(';').forEach { cookie ->
            val separator = cookie.indexOf('=')
            if (separator < 0 || cookie.any { it == '\r' || it == '\n' || it == '\t' }) return@forEach
            val name = cookie.substring(0, separator).trim()
            val value = cookie.substring(separator + 1).trim()
            if (name.isNotEmpty()) appendLine("$domain\tTRUE\t/\tTRUE\t0\t$name\t$value")
        }
    }

    fun isInstagram(url: String): Boolean = runCatching {
        val uri = URI(url)
        val host = uri.host?.lowercase().orEmpty()
        uri.scheme in setOf("http", "https") && (host == "instagram.com" || host.endsWith(".instagram.com"))
    }.getOrDefault(false)

    fun storyMediaPk(url: String): String? = runCatching {
        URI(url).rawQuery.orEmpty().split('&').firstNotNullOfOrNull { part ->
            if (URLDecoder.decode(part.substringBefore('='), "UTF-8") != "story_media_id") null
            else URLDecoder.decode(part.substringAfter('=', ""), "UTF-8")
                .substringBefore('_').takeIf { it.matches(Regex("[0-9]+")) }
        }
    }.getOrNull()

    /** yt-dlp hikaye parcasinin id'si pk degil, pk'nin Instagram kisa kodu (_pk_to_id). */
    fun storyMediaCode(url: String): String? = storyMediaPk(url)?.toBigIntegerOrNull()?.let { pk ->
        val alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        var rest = pk
        val base = 64.toBigInteger()
        buildString {
            do {
                append(alphabet[rest.mod(base).toInt()])
                rest = rest.divide(base)
            } while (rest.signum() > 0)
        }.reversed()
    }

    fun hasSession(cookieHeader: String?): Boolean {
        if (cookieHeader.isNullOrBlank()) return false
        return cookieHeader.split(';').any { cookie ->
            val sep = cookie.indexOf('=')
            if (sep < 0) false
            else {
                val name = cookie.substring(0, sep).trim()
                val value = cookie.substring(sep + 1).trim()
                name == "sessionid" && value.isNotBlank()
            }
        }
    }

    fun hasSession(): Boolean = runCatching {
        val cookies = CookieManager.getInstance().getCookie("https://www.instagram.com")
        hasSession(cookies)
    }.getOrDefault(false)

    fun clearSession(context: Context? = null) {
        runCatching {
            val cm = CookieManager.getInstance()
            cm.setCookie("https://www.instagram.com", "sessionid=; Expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; domain=.instagram.com")
            cm.setCookie("https://www.instagram.com", "ds_user_id=; Expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; domain=.instagram.com")
            cm.flush()
        }
        context?.let { ctx ->
            runCatching {
                File(ctx.cacheDir, "afutube-ig-cookies.txt").delete()
            }
        }
    }

    fun writeFor(context: Context, url: String): File? {
        if (!isInstagram(url)) return null
        return runCatching {
            val cookies = CookieManager.getInstance().getCookie("https://www.instagram.com")
            if (cookies.isNullOrBlank()) return@runCatching null
            File(context.cacheDir, "afutube-ig-cookies.txt").apply { writeText(toNetscape(cookies)) }
        }.getOrNull()
    }
}
