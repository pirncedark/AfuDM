package com.afudm.afutube.feature.home

import org.junit.Assert.assertEquals
import org.junit.Test

class HomeAnalysisMessageTest {
    @Test
    fun `message is specific to YouTube and general for other links`() {
        assertEquals("YouTube ba\u011flant\u0131s\u0131 analiz edilemedi.", analysisErrorMessage("https://youtube.com/watch?v=x"))
        assertEquals("Bu ba\u011flant\u0131 analiz edilemedi.", analysisErrorMessage("https://example.com/video"))
    }
}
