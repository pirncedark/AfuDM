package com.afudm.afutube.runtime

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MediaRuntimeHealthTest {
    @Test
    fun `installed recent engine passes offline health check`() {
        val health = MediaRuntimeHealthChecker.check("2026.01.15")

        assertTrue(health.healthy)
        assertFalse(health.requiresExtractorUpdate)
    }

    @Test
    fun `missing or critical old engine requests mandatory update`() {
        assertTrue(MediaRuntimeHealthChecker.check(null).requiresExtractorUpdate)
        assertTrue(MediaRuntimeHealthChecker.check("2023.12.01").requiresExtractorUpdate)
    }

    @Test
    fun `health test includes an offline YouTube URL matching check`() {
        val health = MediaRuntimeHealthChecker.check("2026.01.15")

        assertTrue(health.details.contains("URL"))
        assertTrue(health.healthy)
    }
}
