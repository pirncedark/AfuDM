package com.afudm.afutube.feature.formats

import com.afudm.afutube.core.extractor.MediaFormat
import java.util.Locale

/** Pure Kotlin mapping from extractor rows to a small, stable set of download choices. */
data class FormatOption(
    val label: String,
    val formatId: String,
    val estimatedSize: String = "",
    val height: Int? = null,
    val mergeAV: Boolean = true,
    val audioFormat: String? = null,
    val sourceFormat: MediaFormat? = null
) {
    companion object {
        const val MP3 = "mp3"
        const val M4A = "m4a"
    }
}

data class SimplifiedFormats(
    val videoOptions: List<FormatOption>,
    val audioOptions: List<FormatOption>,
    val defaultVideoOption: FormatOption?
) {
    val hasAudio: Boolean get() = audioOptions.isNotEmpty()
}

object FormatSimplifier {
    private val standardHeights = listOf(1080, 720, 480)
    private val heightInResolution = Regex("(?:x|×)(\\d{3,4})(?:\\D|$)", RegexOption.IGNORE_CASE)
    private val heightInQuality = Regex("(?:^|\\D)(\\d{3,4})p(?:\\D|$)", RegexOption.IGNORE_CASE)

    fun simplify(formats: List<MediaFormat>): SimplifiedFormats {
        val videos = formats.filterNot { it.isAudioOnly }
        val audios = formats.filter { it.isAudioOnly || (it.acodec.isNotBlank() && it.acodec != "none") }
            // Dogrudan .mp4 gibi kaynaklarda yt-dlp codec bilgisini bos/"none" birakir; kullanici her zaman
            // MP4 + MP3 istiyor. Dosyada ses yoksa indirme karti yt-dlp hatasini gosterir.
            .ifEmpty { formats }
        val heights = videos.mapNotNull(::heightOf)
        val bestAudioSize = (formats.filter { it.isAudioOnly }.ifEmpty { audios })
            .maxOfOrNull { it.fileSizeB.coerceAtLeast(0L) } ?: 0L

        val videoOptions = if (videos.isEmpty()) emptyList() else if (heights.isEmpty()) {
            listOf(FormatOption("En iyi kalite", "best", estimatedSize = estimateSize(videos.maxOfOrNull { it.fileSizeB } ?: 0L), height = null))
        } else {
            val levels = standardHeights.filter { target -> heights.any { it >= target } }
                .ifEmpty { listOf(heights.maxOrNull()!!) }
            levels.map { target ->
                val matching = videos.filter { (heightOf(it) ?: Int.MIN_VALUE) <= target }
                val separateVideo = matching.filter { it.acodec == "none" }
                val bestVideoSize = separateVideo.maxOfOrNull { it.fileSizeB.coerceAtLeast(0L) }
                    ?: matching.maxOfOrNull { it.fileSizeB.coerceAtLeast(0L) } ?: 0L
                val includedAudio = separateVideo.isEmpty() && matching.any { it.acodec.isNotBlank() && it.acodec != "none" }
                val fps = videos.filter { heightOf(it) == target }.maxOfOrNull { it.fps } ?: 0
                val label = "${target}p" + if (fps >= 60) " 60" else ""
                FormatOption(
                    label = label,
                    formatId = "bestvideo[height<=$target][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=$target]+bestaudio/best[height<=$target]/best",
                    estimatedSize = estimateSize(bestVideoSize + if (includedAudio) 0L else bestAudioSize),
                    height = target,
                    mergeAV = true
                )
            }
        }

        val audioSize = bestAudioSize
        // Kullanici karari: yalniz MP4 (video) + MP3 (ses).
        val audioOptions = if (audios.isEmpty()) emptyList() else listOf(
            FormatOption("MP3", "bestaudio/best", estimateSize(audioSize), mergeAV = false, audioFormat = FormatOption.MP3)
        )
        val defaultVideo = videoOptions.firstOrNull { it.height == 720 }
            ?: videoOptions.filter { (it.height ?: Int.MAX_VALUE) < 720 }.maxByOrNull { it.height ?: Int.MIN_VALUE }
            ?: videoOptions.firstOrNull()
        return SimplifiedFormats(videoOptions, audioOptions, defaultVideo)
    }

    fun estimateSize(bytes: Long): String {
        if (bytes <= 0) return ""
        val mb = bytes / 1_048_576.0
        return if (mb >= 1024.0) "~${String.format(Locale.US, "%.1f", mb / 1024.0)} GB"
        else "~${mb.roundToLong()} MB"
    }

    private fun heightOf(format: MediaFormat): Int? =
        heightInResolution.find(format.resolution)?.groupValues?.get(1)?.toIntOrNull()
            ?: heightInQuality.find(format.quality)?.groupValues?.get(1)?.toIntOrNull()

    private fun Double.roundToLong(): Long = kotlin.math.round(this).toLong()
}
