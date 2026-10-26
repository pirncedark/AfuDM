package com.afudm.afutube.feature.downloads

import java.io.File
import org.junit.Assert.*
import org.junit.Test

class EditMediaArgsTest {
    @Test fun trimArgsUseExpectedTimesAndOutputName() {
        val input = File("/media/clip.mp4")
        val output = trimOutput(input)
        assertEquals("clip_kirpik.mp4", output.name)
        assertTrue(trimArgs(input, output, 1500, 4500).containsAll(listOf("-ss", "1.500", "-to", "4.500", "-c", "copy")))
    }
    @Test(expected = IllegalArgumentException::class) fun trimRequiresIncreasingRange() { trimArgs(File("a.mp4"), File("b.mp4"), 3, 3) }
    @Test fun musicArgsMixAndNameOutput() {
        val input = File("clip.mp4")
        val output = musicOutput(input)
        assertEquals("clip_muzikli.mp4", output.name)
        val args = addMusicArgs(input, File("song.mp3"), output, true)
        assertTrue(args.contains("-shortest"))
        assertTrue(args.joinToString(" ").contains("volume=0.2"))
    }
    @Test fun muteArgsCopyVideoWithoutAudio() {
        val input = File("clip.mp4")
        val output = muteOutput(input)
        assertEquals("clip_sessiz.mp4", output.name)
        assertEquals(listOf("-y", "-i", input.absolutePath, "-c", "copy", "-an", output.absolutePath), muteArgs(input, output))
    }
    @Test fun audioArgsExtractAacAt192Kbps() {
        val input = File("clip.webm")
        val output = audioOutput(input)
        assertEquals("clip_ses.m4a", output.name)
        assertEquals(listOf("-y", "-i", input.absolutePath, "-vn", "-c:a", "aac", "-b:a", "192k", output.absolutePath), audioArgs(input, output))
    }
}
