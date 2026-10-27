package com.afudm.afutube.feature.editor.engine

import org.junit.Assert.assertEquals
import org.junit.Test

class ExportPolicyTest {
    @Test fun outputNameSanitizesAndAddsEditSuffixWithoutTouchingSource() {
        assertEquals("my_video_edit.mp4", exportFileName("my video.mov"))
        assertEquals("my_video_edit (2).mp4", exportFileName("my video.mov", listOf("my_video_edit.mp4", "my_video_edit (1).mp4")))
    }

    @Test fun qualityKeepsSourceByDefaultAndCapsOnlyWhenChosen() {
        assertEquals(ExportSize(3840, 2160), exportSize(3840, 2160, ExportQuality.SOURCE))
        assertEquals(ExportSize(1920, 1080), exportSize(3840, 2160, ExportQuality.P1080))
        assertEquals(ExportSize(1280, 720), exportSize(3840, 2160, ExportQuality.P720))
        assertEquals(ExportSize(1920, 1080), exportSize(1280, 720, ExportQuality.P1080))
    }

    @Test fun progressIsBoundedAndDoesNotReportCompleteEarly() {
        assertEquals(0, exportProgress(-3))
        assertEquals(99, exportProgress(100))
        assertEquals(42, exportProgress(42))
    }
}
