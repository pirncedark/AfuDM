package com.afudm.afutube.core.extractor

import org.junit.Assert.assertEquals
import org.junit.Test

class UrlNormalizerTest {
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
}
