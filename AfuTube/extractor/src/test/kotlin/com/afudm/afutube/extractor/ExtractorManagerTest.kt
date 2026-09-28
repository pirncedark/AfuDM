package com.afudm.afutube.extractor

import com.afudm.afutube.core.extractor.MediaExtractor
import com.afudm.afutube.core.extractor.MediaInfo
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ExtractorManagerTest {
    @Test
    fun `failed direct extractor falls through to yt-dlp`() = runBlocking {
        var directCalls = 0
        var ytDlpCalls = 0
        val expected = MediaInfo("id", "title", "", "", 0, "https://example/video.mp4", emptyList())
        val direct = object : MediaExtractor {
            override suspend fun supports(url: String) = true
            override suspend fun extract(url: String): MediaInfo { directCalls++; error("HEAD failed") }
        }
        val ytDlp = object : MediaExtractor {
            override suspend fun supports(url: String) = true
            override suspend fun extract(url: String): MediaInfo { ytDlpCalls++; return expected }
        }

        val result = extractWithFallback(listOf(direct, ytDlp), "https://example/video.mp4")

        assertTrue(result.isSuccess)
        assertEquals(expected, result.getOrNull())
        assertEquals(1, directCalls)
        assertEquals(1, ytDlpCalls)
    }
}
