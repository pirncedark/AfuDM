package com.afudm.afutube.downloader

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DownloadPoliciesTest {
    @Test fun exposesPauseResumeAndRetryForWorkStates() {
        assertEquals(DownloadPolicies.Action.PAUSE, DownloadPolicies.actionForState("RUNNING"))
        assertEquals(DownloadPolicies.Action.RESUME, DownloadPolicies.actionForState("CANCELLED"))
        assertEquals(DownloadPolicies.Action.RETRY, DownloadPolicies.actionForState("FAILED"))
        assertEquals(DownloadPolicies.Action.NONE, DownloadPolicies.actionForState("SUCCEEDED"))
    }

    @Test fun detects403And429WithoutMatchingUnrelatedNumbers() {
        assertTrue(DownloadPolicies.isRateLimitedOrForbidden("HTTP Error 403: Forbidden"))
        assertTrue(DownloadPolicies.isRateLimitedOrForbidden("429 Too Many Requests"))
        assertFalse(DownloadPolicies.isRateLimitedOrForbidden("video 4030 is unavailable"))
    }

    @Test fun retriesRateLimitErrorsOnlyUntilThreeTotalAttempts() {
        assertTrue(DownloadPolicies.shouldRetry("403 Forbidden", 0))
        assertTrue(DownloadPolicies.shouldRetry("429 Too Many Requests", 1))
        assertFalse(DownloadPolicies.shouldRetry("429 Too Many Requests", 2))
        assertFalse(DownloadPolicies.shouldRetry("socket timeout", 0))
    }

    @Test fun usesExponentialBackoffForThreeTotalAttempts() {
        assertEquals(1_000L, DownloadPolicies.retryDelayMillis(0))
        assertEquals(2_000L, DownloadPolicies.retryDelayMillis(1))
        assertEquals(2_000L, DownloadPolicies.retryDelayMillis(2))
        assertEquals(2_000L, DownloadPolicies.retryDelayMillis(9))
    }

    @Test fun invalidOrNegativeRateLimitBecomesUnlimited() {
        assertEquals(0, DownloadPolicies.parseRateLimitKbps("0"))
        assertEquals(0, DownloadPolicies.parseRateLimitKbps("-8"))
        assertEquals(0, DownloadPolicies.parseRateLimitKbps("abc"))
        assertEquals(256, DownloadPolicies.parseRateLimitKbps("256"))
    }

    @Test fun buildsAudioMetadataAndRateOptions() {
        assertEquals(
            listOf(
                "--continue" to null,
                "--extract-audio" to null,
                "--audio-format" to "opus",
                "--embed-thumbnail" to null,
                "--embed-chapters" to null,
                "--limit-rate" to "512K"
            ),
            DownloadPolicies.ytDlpOptions("opus", true, true, 512)
        )
    }

    @Test fun extractsDistinctHttpLinksAndStripsTrailingPunctuation() {
        assertEquals(
            listOf("https://example.com/a", "http://example.org/b"),
            DownloadPolicies.extractHttpLinks("Try https://example.com/a, then https://example.com/a and (http://example.org/b).")
        )
    }
}
