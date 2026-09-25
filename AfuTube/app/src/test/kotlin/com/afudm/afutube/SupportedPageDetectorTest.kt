package com.afudm.afutube

import org.junit.Assert.*
import org.junit.Test

class SupportedPageDetectorTest {
    @Test fun recognizesSupportedVideoPagePatterns() {
        listOf(
            "https://www.youtube.com/watch?v=x", "https://youtube.com/shorts/x", "https://m.youtube.com/watch?v=x",
            "https://music.youtube.com/watch?v=x", "https://youtu.be/x", "https://instagram.com/p/abc",
            "https://www.instagram.com/reel/abc/", "https://tiktok.com/@name/video/123", "https://x.com/name/status/123",
            "https://twitter.com/name/status/123", "https://facebook.com/name/videos/123", "https://facebook.com/watch/?v=1",
            "https://facebook.com/reel/123", "https://vimeo.com/123", "https://dailymotion.com/video/abc"
        ).forEach { assertTrue("Expected supported: $it", SupportedPageDetector.supports(it)) }
    }

    @Test fun rejectsNonVideoOrMalformedPages() {
        listOf("https://youtube.com/results?search_query=x", "https://instagram.com/name/", "https://tiktok.com/@name",
            "https://x.com/name", "https://vimeo.com/channels/staffpicks", "javascript:alert(1)", "not a url")
            .forEach { assertFalse("Expected unsupported: $it", SupportedPageDetector.supports(it)) }
    }
}
