package com.afudm.afutube.media

import org.junit.Assert.assertEquals
import org.junit.Test

class MediaFileTypeDetectorTest {
    @Test fun audioExtensionsOpenAsListen() {
        listOf("mp3", "m4a", "opus", "webm", "aac", "flac", "wav", "ogg").forEach {
            assertEquals(it, MediaFileType.AUDIO, MediaFileTypeDetector.fromPath("/tmp/file.$it"))
        }
    }

    @Test fun videoExtensionsOpenAsWatch() {
        listOf("mp4", "mkv", "mov", "avi").forEach {
            assertEquals(it, MediaFileType.VIDEO, MediaFileTypeDetector.fromPath("/tmp/file.$it"))
        }
    }
}
