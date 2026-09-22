package com.afudm.afutube.extractor

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * MediaExtractor — URL'yi analiz eder, mevcut formatları döndürür.
 * Arka planda çalışan lightweight extractor katmanı.
 */
object MediaExtractor {

    private const val API_BASE = "https://afudm-api.vercel.app/api/info"

    suspend fun extract(url: String): ExtractResult = withContext(Dispatchers.IO) {
        try {
            val encodedUrl = java.net.URLEncoder.encode(url, "UTF-8")
            val conn = URL("$API_BASE?url=$encodedUrl").openConnection() as HttpURLConnection
            conn.apply {
                connectTimeout = 15_000
                readTimeout   = 30_000
                requestMethod = "GET"
                setRequestProperty("Accept", "application/json")
                setRequestProperty("User-Agent", "AfuTube/1.0")
            }

            if (conn.responseCode != 200) {
                return@withContext ExtractResult.Error("HTTP ${conn.responseCode}")
            }

            val body = conn.inputStream.bufferedReader().readText()
            val json = JSONObject(body)
            parseResult(json)
        } catch (e: Exception) {
            ExtractResult.Error(e.localizedMessage ?: "Bilinmeyen hata")
        }
    }

    private fun parseResult(json: JSONObject): ExtractResult {
        val title     = json.optString("title", "Başlık bulunamadı")
        val thumbnail = json.optString("thumbnail", "")
        val duration  = json.optInt("duration", 0)
        val uploader  = json.optString("uploader", "")

        val formatsArr = json.optJSONArray("formats") ?: return ExtractResult.Error("Format listesi boş")
        val formats = mutableListOf<MediaFormat>()

        for (i in 0 until formatsArr.length()) {
            val f = formatsArr.getJSONObject(i)
            formats += MediaFormat(
                formatId   = f.optString("format_id"),
                ext        = f.optString("ext"),
                quality    = f.optString("quality"),
                resolution = f.optString("resolution"),
                fileSizeKB = f.optLong("filesize", 0) / 1024,
                hasVideo   = f.optBoolean("vcodec", false),
                hasAudio   = f.optBoolean("acodec", false),
                url        = f.optString("url")
            )
        }

        // En iyi formatlar öne çıkarılır
        val sorted = formats.sortedWith(
            compareByDescending<MediaFormat> { it.hasVideo && it.hasAudio }
                .thenByDescending { it.fileSizeKB }
        )

        return ExtractResult.Success(
            MediaMetadata(
                title     = title,
                thumbnail = thumbnail,
                duration  = duration,
                uploader  = uploader,
                formats   = sorted
            )
        )
    }
}

// ─── Veri modelleri ──────────────────────────────────────────────────────────

data class MediaMetadata(
    val title     : String,
    val thumbnail : String,
    val duration  : Int,          // saniye
    val uploader  : String,
    val formats   : List<MediaFormat>
)

data class MediaFormat(
    val formatId   : String,
    val ext        : String,
    val quality    : String,
    val resolution : String,
    val fileSizeKB : Long,
    val hasVideo   : Boolean,
    val hasAudio   : Boolean,
    val url        : String
) {
    /** Kullanıcıya gösterilen etiket */
    val label: String get() = buildString {
        if (resolution.isNotBlank()) append(resolution)
        else append(quality.ifBlank { ext.uppercase() })
        if (fileSizeKB > 0) append("  •  ${fileSizeKB / 1024} MB")
        if (!hasVideo) append("  🎵 Ses")
    }
}

sealed class ExtractResult {
    data class Success(val metadata: MediaMetadata) : ExtractResult()
    data class Error(val message: String)           : ExtractResult()
}
