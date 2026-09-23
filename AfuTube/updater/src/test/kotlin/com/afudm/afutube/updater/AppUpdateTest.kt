package com.afudm.afutube.updater

import java.nio.file.Files
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class AppUpdateTest {
    @Test
    fun `release parser selects newest AfuTube release and ignores desktop tags`() {
        val json = """
            [
              {"tag_name":"v99.0.0","body":"desktop","assets":[]},
              {"tag_name":"afutube-v1.1.0","body":"Türkçe not","assets":[
                {"name":"AfuTube-universal.apk","browser_download_url":"https://example/apk"},
                {"name":"AfuTube-universal.apk.sha256","browser_download_url":"https://example/sha"}
              ]},
              {"tag_name":"afutube-v1.0.0","body":"old","assets":[]}
            ]
        """.trimIndent()

        val update = AppUpdateParser.latest(json, currentVersionCode = 1000000)

        assertNotNull(update)
        assertEquals("1.1.0", update.versionName)
        assertTrue(update.versionCode > 1000000)
        assertEquals("https://example/apk", update.apkUrl)
        assertEquals("https://example/sha", update.checksumUrl)
    }

    @Test
    fun `release parser returns no update for same or older version`() {
        val json = """[{"tag_name":"afutube-v1.0.0","body":"old","assets":[]}]"""

        assertEquals(null, AppUpdateParser.latest(json, currentVersionCode = 1000000))
    }

    @Test
    fun `sha256 verifier accepts expected digest and rejects a mismatch`() {
        val file = Files.createTempFile("afutube", ".apk")
        Files.write(file, "AfuTube".toByteArray())
        val digest = MessageDigest.getInstance("SHA-256")
            .digest("AfuTube".toByteArray()).joinToString("") { "%02x".format(it) }

        assertTrue(Sha256.verify(file, digest))
        assertFalse(Sha256.verify(file, "0".repeat(64)))
        Files.deleteIfExists(file)
    }
}
