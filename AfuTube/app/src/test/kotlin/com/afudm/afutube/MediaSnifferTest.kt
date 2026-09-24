package com.afudm.afutube

import org.junit.Assert.*
import org.junit.Test

class MediaSnifferTest {
    @Test fun classifiesSupportedUrlsAndTypes() {
        assertEquals(MediaSniffer.Kind.HLS, MediaSniffer.classify("https://a.test/live.m3u8?token=x"))
        assertEquals(MediaSniffer.Kind.DASH, MediaSniffer.classify("https://a.test/play?id=1", "application/dash+xml"))
        assertEquals(MediaSniffer.Kind.MP4, MediaSniffer.classify("https://a.test/movie", "video/mp4"))
        assertNull(MediaSniffer.classify("https://a.test/image.jpg", "image/jpeg"))
    }
    @Test fun rejectsUntrustedSchemesAndMalformedUrls() {
        assertFalse(MediaSniffer.isHttpUrl("javascript:alert(1)"))
        assertFalse(MediaSniffer.isHttpUrl("blob:https://a.test/id"))
        assertFalse(MediaSniffer.isHttpUrl("https://" + "x".repeat(4097)))
    }
    @Test fun filtersSegmentsAndSmallRanges() {
        assertTrue(MediaSniffer.isSegment("https://a.test/chunk.ts"))
        assertTrue(MediaSniffer.isSegment("https://a.test/movie.mp4", true))
        assertFalse(MediaSniffer.isSegment("https://a.test/movie.mp4"))
    }
    @Test fun readsMasterResolutionAndBandwidth() {
        val list = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=2000000,RESOLUTION=1280x720\nv.m3u8\n#EXT-X-STREAM-INF:BANDWIDTH=800000\na.m3u8"
        assertEquals(listOf("720p", "800 kbps"), MediaSniffer.masterQualities(list))
        assertTrue(MediaSniffer.masterQualities("x".repeat(300000)).isEmpty())
        assertEquals(setOf("https://a.test/hls/720p/index.m3u8"), MediaSniffer.masterVariants("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=8,RESOLUTION=640x360\n720p/index.m3u8", "https://a.test/hls/master.m3u8"))
    }
}
