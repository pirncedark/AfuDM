package com.afudm.afutube.extractor

import com.afudm.afutube.core.diagnostics.AnalysisErrorCategory
import com.afudm.afutube.core.diagnostics.AnalysisFailure
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AnalysisErrorClassifierTest {
    @Test
    fun `classifies forbidden errors and preserves exit code`() {
        val error = AnalysisFailure(
            message = "HTTP Error 403: Forbidden",
            exitCode = 1,
            traceback = "ERROR: HTTP Error 403: Forbidden"
        ).toAnalysisError("2026.09.0")

        assertEquals(AnalysisErrorCategory.ACCESS_403, error.category)
        assertEquals(1, error.exitCode)
        assertTrue(error.traceback.contains("403"))
        assertEquals("2026.09.0", error.ytDlpVersion)
    }

    @Test
    fun `classifies parser errors separately from extractor errors`() {
        val error = AnalysisFailure(
            message = "Unable to parse video information",
            traceback = "org.json.JSONException: end of input"
        ).toAnalysisError("unknown")

        assertEquals(AnalysisErrorCategory.PARSE, error.category)
    }
}
