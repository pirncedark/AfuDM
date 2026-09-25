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
    @Test fun filtersAdHostsAndAdPathsIncludingSubdomains() {
        listOf(
            "https://doubleclick.net/video.mp4", "https://secure.googlesyndication.com/a.m3u8",
            "https://googleadservices.com/a.mp4", "https://googleads.g.doubleclick.net/a.mp4",
            "https://imasdk.googleapis.com/a.mp4", "https://pagead2.googlesyndication.com/a.mp4",
            "https://adservice.google.com/a.mp4", "https://g.doubleclick.net/a.mp4", "https://2mdn.net/a.mp4",
            "https://adnxs.com/a.mp4", "https://pubmatic.com/a.mp4", "https://springserve.com/a.mp4",
            "https://spotxchange.com/a.mp4", "https://teads.tv/a.mp4", "https://criteo.com/a.mp4",
            "https://rubiconproject.com/a.mp4", "https://taboola.com/a.mp4", "https://outbrain.com/a.mp4",
            "https://innovid.com/a.mp4", "https://serving-sys.com/a.mp4", "https://moatads.com/a.mp4",
            "https://cdn.example.com/vast/preroll.mp4", "https://cdn.example.com/ads/video.mp4",
            "https://cdn.example.com/video/adtag/clip.mp4"
        ).forEach { assertTrue("Expected filtered: $it", MediaSniffer.isAdOrTrackingRequest(it)) }
        assertFalse(MediaSniffer.isAdOrTrackingRequest("https://doubleclick.net.evil.test/clip.mp4"))
        assertFalse(MediaSniffer.isAdOrTrackingRequest("https://cdn.example.com/clip.mp4"))
    }
    @Test fun filtersYoutubeMediaTrafficOnlyOnYoutubePages() {
        assertTrue(MediaSniffer.shouldIgnoreRequest("https://r1.googlevideo.com/videoplayback", "https://www.youtube.com/watch?v=x"))
        assertTrue(MediaSniffer.shouldIgnoreRequest("https://www.youtube.com/api/video.m3u8", "https://youtu.be/x"))
        assertFalse(MediaSniffer.shouldIgnoreRequest("https://r1.googlevideo.com/videoplayback", "https://example.com/watch"))
    }
    @Test fun ranksSameSiteMastersAndLargeCandidatesFirst() {
        val candidates = listOf(
            MediaSniffer.Candidate("https://other.test/movie.mp4", MediaSniffer.Kind.MP4, size = 5000),
            MediaSniffer.Candidate("https://cdn.site.test/master.m3u8", MediaSniffer.Kind.HLS),
            MediaSniffer.Candidate("https://site.test/small.mp4", MediaSniffer.Kind.MP4, size = 100),
            MediaSniffer.Candidate("https://site.test/large.mp4", MediaSniffer.Kind.MP4, size = 900)
        )
        assertEquals(listOf("https://cdn.site.test/master.m3u8", "https://site.test/large.mp4", "https://site.test/small.mp4", "https://other.test/movie.mp4"),
            MediaSniffer.rankCandidates(candidates, "https://www.site.test/watch" ).map { it.url })
    }
    @Test fun readsMasterResolutionAndBandwidth() {
        val list = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=2000000,RESOLUTION=1280x720\nv.m3u8\n#EXT-X-STREAM-INF:BANDWIDTH=800000\na.m3u8"
        assertEquals(listOf("720p", "800 kbps"), MediaSniffer.masterQualities(list))
        assertTrue(MediaSniffer.masterQualities("x".repeat(300000)).isEmpty())
        assertEquals(setOf("https://a.test/hls/720p/index.m3u8"), MediaSniffer.masterVariants("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=8,RESOLUTION=640x360\n720p/index.m3u8", "https://a.test/hls/master.m3u8"))
    }
}
