package com.afudm.afutube.core.diagnostics

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SensitiveDataRedactorTest {
    @Test
    fun `redacts headers and secret query values while keeping traceback useful`() {
        val raw = """
            Cookie: SID=secret-cookie
            Authorization: Bearer secret-auth
            https://youtube.com/watch?v=abc&token=secret-token&list=playlist
        """.trimIndent()

        val redacted = SensitiveDataRedactor.redact(raw)

        assertFalse(redacted.contains("secret-cookie"))
        assertFalse(redacted.contains("secret-auth"))
        assertFalse(redacted.contains("secret-token"))
        assertTrue(redacted.contains("token=<redacted>"))
        assertTrue(redacted.contains("list=playlist"))
    }
}
