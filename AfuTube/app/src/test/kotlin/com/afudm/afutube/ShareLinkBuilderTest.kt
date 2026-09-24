package com.afudm.afutube

import kotlin.test.Test
import kotlin.test.assertEquals

class ShareLinkBuilderTest {
    @Test
    fun `release version uses direct universal APK link`() {
        assertEquals(
            "https://github.com/pirncedark/AfuDM/releases/download/afutube-v1.3.1/AfuTube-universal.apk",
            ShareLinkBuilder.url("1.3.1")
        )
    }

    @Test
    fun `development versions use releases page`() {
        assertEquals("https://github.com/pirncedark/AfuDM/releases", ShareLinkBuilder.url("0.0.57"))
        assertEquals("https://github.com/pirncedark/AfuDM/releases", ShareLinkBuilder.url("1.3.1-debug"))
    }
}
