package com.afudm.afutube.feature.formats

import com.afudm.afutube.core.extractor.MediaFormat
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FormatSimplifierTest {
    @Test
    fun simplifiesThirtyCodecVariantsIntoSixVideoAndTwoAudioChoices() {
        val formats = buildList {
            listOf(2160, 1440, 1080, 720, 480, 360).forEach { height ->
                listOf("vp9", "avc1", "av01", "vp9").forEachIndexed { codecIndex, codec ->
                    add(format("v$height-$codecIndex", height, fps = if (height == 1080 && codecIndex == 0) 60 else 30,
                        codec = codec, size = height * 10_000L))
                }
            }
            add(audio("opus", "webm", 3_000_000))
            add(audio("m4a", "m4a", 4_000_000))
            add(audio("aac", "mp4", 2_000_000))
            add(audio("opus-2", "webm", 3_500_000))
            add(format("muxed", 720, audioCodec = "mp4a", size = 10_000_000))
            add(format("muxed2", 480, audioCodec = "mp4a", size = 8_000_000))
        }

        val result = FormatSimplifier.simplify(formats)

        assertEquals(30, formats.size)
        assertEquals(listOf(2160, 1440, 1080, 720, 480, 360), result.videoOptions.map { it.height })
        assertEquals(8, result.videoOptions.size + result.audioOptions.size)
        assertEquals("2160p (4K)", result.videoOptions.first().label)
        assertEquals("1080p 60", result.videoOptions[2].label)
        assertTrue(result.videoOptions[3].formatId.contains("bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"))
        assertTrue(result.videoOptions[3].mergeAV)
        assertEquals(FormatOption.MP3, result.audioOptions[0].audioFormat)
        assertEquals(FormatOption.M4A, result.audioOptions[1].audioFormat)
        assertEquals("~11 MB", result.videoOptions[3].estimatedSize)
        assertEquals("~4 MB", result.audioOptions[0].estimatedSize)
        assertEquals(result.videoOptions[3], result.defaultVideoOption)
    }

    @Test
    fun directVideoWithoutHeightOffersBestQualityAndAudioChoices() {
        val result = FormatSimplifier.simplify(listOf(format("direct", null, size = 12_000_000), audio("a", "m4a", 4_000_000)))

        assertEquals(listOf("En iyi kalite"), result.videoOptions.map { it.label })
        assertEquals("best", result.videoOptions.single().formatId)
        assertEquals(2, result.audioOptions.size)
    }

    @Test
    fun showsHighestAvailableFallbackAndDefaultsTo720WhenThatStepExists() {
        val lowOnly = FormatSimplifier.simplify(listOf(format("low", 240)))
        assertEquals(listOf(240), lowOnly.videoOptions.map { it.height })
        val mixed = FormatSimplifier.simplify(listOf(format("1080", 1080), format("480", 480)))
        assertEquals(720, mixed.defaultVideoOption?.height)
    }

    @Test
    fun keepsAudioSectionEmptyWhenNoAudioIsAvailable() {
        val result = FormatSimplifier.simplify(listOf(format("video", 720, audioCodec = "none")))
        assertTrue(result.audioOptions.isEmpty())
        assertFalse(result.hasAudio)
    }

    private fun format(id: String, height: Int?, fps: Int = 30, codec: String = "avc1", audioCodec: String = "none", size: Long = 0) =
        MediaFormat(id, "mp4", height?.let { "${it}p" } ?: "direct", height?.let { "1920x$it" } ?: "", fps,
            codec, audioCodec, size, "https://example.com/$id")

    private fun audio(id: String, ext: String, size: Long) =
        MediaFormat(id, ext, "audio-only", "", 0, "none", "opus", size, "https://example.com/$id")
}
