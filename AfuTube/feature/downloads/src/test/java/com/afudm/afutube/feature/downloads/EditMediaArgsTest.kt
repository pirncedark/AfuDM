package com.afudm.afutube.feature.downloads

import java.io.File
import org.junit.Assert.*
import org.junit.Test

class EditMediaArgsTest {
    @Test fun trimArgsUseExpectedTimesAndOutputName() {
        val input = File("/media/clip.mp4"); val output = trimOutput(input)
        assertEquals("clip_kirpik.mp4", output.name)
        assertTrue(trimArgs(input, output, 1500, 4500).containsAll(listOf("-ss", "1.500", "-t", "3.000", "-c:a", "copy")))
    }
    @Test(expected = IllegalArgumentException::class) fun trimRequiresIncreasingRange() { editArgs(File("a.mp4"), File("b.mp4"), 3, 3, null, 100, 100) }
    @Test fun musiclessArgsKeepVideoAndAudio() {
        val args = editArgs(File("clip.mp4"), File("out.mp4"), 0, 2000, null, 100, 100)
        assertTrue(args.containsAll(listOf("-c:v", "copy", "-c:a", "copy", "-t", "2.000")))
    }
    @Test fun musicArgsMixAtSelectedVolumes() {
        val args = editArgs(File("clip.mp4"), File("out.mp4"), 500, 5000, File("song.mp3"), 30, 75)
        assertTrue(args.contains("[0:a]volume=0.3[orig];[1:a]volume=0.75[music];[orig][music]amix=inputs=2:duration=first:dropout_transition=2[a]"))
        assertTrue(args.containsAll(listOf("-ss", "0.500", "-t", "4.500", "-map", "[a]")))
    }
    @Test fun zeroOriginalVolumeKeepsMusicOnly() {
        val args = editArgs(File("clip.mp4"), File("out.mp4"), 0, Long.MAX_VALUE, File("song.mp3"), 0, 100)
        assertTrue(args.contains("[1:a]volume=1.0[a]")); assertFalse(args.contains("[0:a]"))
    }
    @Test fun videoWithoutAudioMapsMusicTrack() {
        val args = editArgs(File("silent.mp4"), File("out.mp4"), 0, 1000, File("song.mp3"), 100, 100, false)
        assertTrue(args.contains("[1:a]volume=1.0[a]")); assertFalse(args.contains("[0:a]"))
    }
    @Test fun outputCannotOverwriteInput() {
        try { editArgs(File("a.mp4"), File("a.mp4"), 0, 1, null, 100, 100); fail("Expected rejection") } catch (_: IllegalArgumentException) { }
    }
}
