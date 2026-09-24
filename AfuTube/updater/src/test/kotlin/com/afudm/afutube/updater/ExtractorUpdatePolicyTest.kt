package com.afudm.afutube.updater

import com.afudm.afutube.core.diagnostics.AnalysisErrorCategory
import com.yausername.youtubedl_android.YoutubeDL
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger

class ExtractorUpdatePolicyTest {
    @Test
    fun `failed automatic update can retry after one hour but is throttled before then`() {
        assertFalse(ExtractorUpdatePolicy.canAutoRetry(10_000L, 10_000L + ExtractorUpdatePolicy.RETRY_MS - 1))
        assertTrue(ExtractorUpdatePolicy.canAutoRetry(10_000L, 10_000L + ExtractorUpdatePolicy.RETRY_MS))
    }

    @Test
    fun `extractor rate limit error is a calm Turkish message`() {
        assertEquals("Motor güncellemesi şu an yapılamadı, sonra tekrar denenecek.",
            ExtractorUpdatePolicy.displayError(IllegalStateException("GitHub API HTTP 403 rate limit")))
    }
    @Test
    fun `only extractor family is eligible for stale one retry`() {
        val old = 10L
        val now = old + ExtractorUpdatePolicy.DAY_MS
        assertTrue(ExtractorUpdatePolicy.shouldUpdateForAnalysis(AnalysisErrorCategory.EXTRACTOR, old, now))
        assertTrue(ExtractorUpdatePolicy.shouldUpdateForAnalysis(AnalysisErrorCategory.PARSE, old, now))
        assertFalse(ExtractorUpdatePolicy.shouldUpdateForAnalysis(AnalysisErrorCategory.ACCESS_403, old, now))
        assertFalse(ExtractorUpdatePolicy.shouldUpdateForAnalysis(AnalysisErrorCategory.NETWORK_TIMEOUT, old, now))
    }

    @Test
    fun `manual policy bypasses daily gate through stale predicate`() {
        val now = 1_000_000L
        assertFalse(ExtractorUpdatePolicy.isStale(now - 1_000L, now))
        assertTrue(ExtractorUpdatePolicy.isStale(0L, now))
    }

    @Test
    fun `fake updater receives the selected stable and nightly channels`() = runBlocking {
        assertSame(YoutubeDL.UpdateChannel.STABLE, ExtractorUpdater.libraryChannel(ExtractorUpdater.Channel.STABLE))
        assertSame(YoutubeDL.UpdateChannel.NIGHTLY, ExtractorUpdater.libraryChannel(ExtractorUpdater.Channel.NIGHTLY))
    }

    @Test
    fun `two concurrent calls perform one update at a time`() = runBlocking {
        val calls = AtomicInteger(0)
        val coordinator = ExtractorUpdateCoordinator<Any>(
            version = { "2026.01" },
            update = { _, _ ->
                calls.incrementAndGet()
                delay(20)
                YoutubeDL.UpdateStatus.ALREADY_UP_TO_DATE
            }
        )

        val results = (1..2).map { async { coordinator.update(Any(), ExtractorUpdater.Channel.STABLE, now = 1_000L) } }.awaitAll()

        assertEquals(2, results.size)
        assertEquals(1, calls.get())
        assertFalse(results[1].attempted)
    }

    @Test
    fun `force update bypasses coordinator daily gate`() = runBlocking {
        val calls = AtomicInteger(0)
        val coordinator = ExtractorUpdateCoordinator<Any>(
            version = { "2026.01" },
            update = { _, _ -> calls.incrementAndGet(); YoutubeDL.UpdateStatus.ALREADY_UP_TO_DATE }
        )

        coordinator.update(Any(), ExtractorUpdater.Channel.STABLE, now = 1_000L)
        coordinator.update(Any(), ExtractorUpdater.Channel.STABLE, force = true, now = 1_001L)

        assertEquals(2, calls.get())
    }
}
