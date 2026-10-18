package com.afudm.afutube.core.extractor

import org.junit.Assert.assertEquals
import org.junit.Test

class UrlClassifierTest {
    @Test
    fun `normalizes uppercase host before removing www prefix`() {
        assertEquals(UrlType.DIRECT_VIDEO, UrlClassifier.classify("https://WWW.Example.com/video.mp4"))
    }
}
