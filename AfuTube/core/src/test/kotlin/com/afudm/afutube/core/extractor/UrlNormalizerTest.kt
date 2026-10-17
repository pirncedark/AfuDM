package com.afudm.afutube.core.extractor

import org.junit.Assert.assertEquals
import org.junit.Test

class UrlNormalizerTest {
    @Test
    fun `converts Instagram highlight share and preserves requested story`() {
        assertEquals(
            "https://www.instagram.com/stories/highlights/18072912233468488/?story_media_id=4002849496279096279_1581116288",
            UrlNormalizer.normalize("https://www.instagram.com/s/aGlnaGxpZ2h0OjE4MDcyOTEyMjMzNDY4NDg4?story_media_id=4002849496279096279_1581116288&cplk=MWw2bGMzZW9pZnlscA==&igsh=tracking&utm_source=share")
        )
    }

    @Test
    fun `keeps previous behavior for invalid Instagram share`() {
        assertEquals(
            "https://www.instagram.com/s/invalid!/?cplk=keep",
            UrlNormalizer.normalize("https://www.instagram.com/s/invalid!/?cplk=keep&utm_source=share")
        )
    }

    @Test
    fun `accepts padded and unpadded highlight shares`() {
        listOf("aGlnaGxpZ2h0OjEyMw==", "aGlnaGxpZ2h0OjEyMw").forEach { encoded ->
            assertEquals(
                "https://www.instagram.com/stories/highlights/123/",
                UrlNormalizer.normalize("https://instagram.com/s/$encoded")
            )
        }
    }

    @Test
    fun `keeps non highlight Instagram shares unchanged`() {
        assertEquals(
            "https://instagram.com/s/b3RoZXI6MTIz?igsh=keep",
            UrlNormalizer.normalize("https://instagram.com/s/b3RoZXI6MTIz?igsh=keep")
        )
    }

    @Test
    fun `converts youtu be and removes share tracking`() {
        assertEquals(
            "https://www.youtube.com/watch?v=Wz4qYO-91zg",
            UrlNormalizer.normalize("https://youtu.be/Wz4qYO-91zg?si=secret&feature=share")
        )
    }

    @Test
    fun `converts shorts and mobile watch links`() {
        assertEquals(
            "https://www.youtube.com/watch?v=abc123",
            UrlNormalizer.normalize("https://www.youtube.com/shorts/abc123?pp=abc")
        )
        assertEquals(
            "https://www.youtube.com/watch?v=abc123",
            UrlNormalizer.normalize("https://m.youtube.com/watch?v=abc123&utm_source=x")
        )
    }

    @Test
    fun `removes utm but preserves playlist and time parameters`() {
        assertEquals(
            "https://www.youtube.com/watch?v=abc123&list=PL123&index=2&t=42&start=5",
            UrlNormalizer.normalize("https://youtube.com/watch?v=abc123&si=drop&list=PL123&index=2&utm_medium=x&t=42&start=5")
        )
    }

    @Test
    fun `removes only utm and si tracking parameters on non YouTube hosts`() {
        assertEquals(
            "https://example.com/watch?keep=1&feature=share",
            UrlNormalizer.normalize("https://example.com/watch?utm_source=x&keep=1&si=abc&feature=share")
        )
    }
}
