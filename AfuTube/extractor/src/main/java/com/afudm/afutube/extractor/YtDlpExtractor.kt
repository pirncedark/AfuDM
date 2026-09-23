package com.afudm.afutube.extractor

import android.content.Context
import com.afudm.afutube.core.extractor.MediaExtractor
import com.afudm.afutube.core.extractor.MediaFormat
import com.afudm.afutube.core.extractor.MediaInfo
import com.afudm.afutube.runtime.MediaRuntime
import com.yausername.youtubedl_android.YoutubeDL
import com.yausername.youtubedl_android.YoutubeDLRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

/**
 * youtubedl-android kütüphanesi üzerinden yt-dlp çalıştıran extractor.
 * 1800+ siteyi destekler.
 */
class YtDlpExtractor(private val context: Context) : MediaExtractor {

    /**
     * yt-dlp hemen hemen her URL'yi deneyebilir.
     * DirectUrlExtractor zaten direct file URL'leri önce yakalar.
     */
    override suspend fun supports(url: String): Boolean = true

    override suspend fun extract(url: String): MediaInfo = withContext(Dispatchers.IO) {
        MediaRuntime.ensureInitialized(context)
        val request = YoutubeDLRequest(url).apply {
            addOption("--dump-json")
            addOption("--no-playlist")
            addOption("--no-warnings")
            addOption("--socket-timeout", "15")
        }

        val response = YoutubeDL.getInstance().execute(request)

        if (response.exitCode != 0) {
            throw RuntimeException("yt-dlp hatası (${response.exitCode}): ${response.err}")
        }

        parseJson(JSONObject(response.out.trim()))
    }

    private fun parseJson(json: JSONObject): MediaInfo {
        val formats = parseFormats(json.optJSONArray("formats"))

        return MediaInfo(
            id        = json.optString("id", ""),
            title     = json.optString("title", "Başlıksız"),
            thumbnail = json.optString("thumbnail", ""),
            uploader  = json.optString("uploader", json.optString("channel", "")),
            duration  = json.optInt("duration", 0),
            sourceUrl = json.optString("webpage_url", json.optString("url", "")),
            formats   = formats
        )
    }

    private fun parseFormats(arr: JSONArray?): List<MediaFormat> {
        if (arr == null) return emptyList()

        val list = mutableListOf<MediaFormat>()
        for (i in 0 until arr.length()) {
            val f = arr.getJSONObject(i)
            val vcodec = f.optString("vcodec", "none")
            val acodec = f.optString("acodec", "none")

            // Gerçek URL olmayan formatları atla
            val url = f.optString("url", "")
            if (url.isBlank()) continue

            list += MediaFormat(
                formatId   = f.optString("format_id"),
                ext        = f.optString("ext", "mp4"),
                quality    = f.optString("format_note", ""),
                resolution = f.optString("resolution", ""),
                fps        = f.optInt("fps", 0),
                vcodec     = vcodec,
                acodec     = acodec,
                fileSizeB  = f.optLong("filesize", f.optLong("filesize_approx", 0L)),
                url        = url
            )
        }

        // Sıralama: önce video+audio, sonra video-only, sonra audio-only; boyuta göre büyükten küçüğe
        return list.sortedWith(
            compareByDescending<MediaFormat> { it.vcodec != "none" && it.acodec != "none" }
                .thenByDescending { it.vcodec != "none" }
                .thenByDescending { it.fileSizeB }
        )
    }
}
