package com.afudm.afutube.feature.editor.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class TimelineMathTest {
    private val clips = listOf(VideoClip("a", "a.mp4", 2_000), VideoClip("b", "b.mp4", 4_000, speed = 2.0))

    @Test fun findsClipAndSourcePositionAtPlayhead() {
        assertEquals(TimelineMath.ClipPosition(0, 1_000), TimelineMath.clipAtPlayhead(clips, 1_000))
        assertEquals(TimelineMath.ClipPosition(1, 1_000), TimelineMath.clipAtPlayhead(clips, 2_500))
    }

    @Test fun splitRejectsClipEdges() {
        assertNull(TimelineMath.splitOffset(clips.first(), 50))
        assertEquals(1_000L, TimelineMath.splitOffset(clips.first(), 1_000))
    }

    @Test fun rmsSamplesAndZoomAreStable() {
        assertEquals(listOf(1f, 0f), TimelineMath.rms(shortArrayOf(32767, 32767, 0, 0), 2).map { if (it > .99f) 1f else 0f })
        assertEquals(.01f, TimelineMath.pixelsPerMillisecond(1_000f, 100_000, 1f), .0001f)
    }

    @Test fun fixedRmsBucketsHandleSilenceAndConstantAmplitude() {
        assertEquals(List(200) { 0f }, TimelineMath.rmsBuckets(ShortArray(0), 200))
        assertEquals(List(4) { 0f }, TimelineMath.rmsBuckets(ShortArray(20), 4))
        val buckets = TimelineMath.rmsBuckets(ShortArray(20) { 16384 }, 4)
        assertEquals(4, buckets.size)
        buckets.forEach { assertEquals(.5f, it, .001f) }
    }
}
