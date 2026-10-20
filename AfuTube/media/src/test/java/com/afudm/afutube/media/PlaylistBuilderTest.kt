package com.afudm.afutube.media

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class PlaylistBuilderTest {
    @get:Rule val folder = TemporaryFolder()

    private fun media(name: String, modified: Long): File = folder.newFile(name).apply {
        assertTrue(setLastModified(modified))
    }

    @Test fun newestFirstAndOpenedFileIndex() {
        val old = media("old.mp4", 10_000)
        val opened = media("opened.mp3", 20_000)
        val newest = media("newest.webm", 30_000)

        val playlist = PlaylistBuilder.build(opened)

        assertEquals(listOf(newest, opened, old), playlist.files)
        assertEquals(1, playlist.startIndex)
    }

    @Test fun excludesUnsupportedFilesAndDirectories() {
        val opened = media("opened.MP4", 10_000)
        val audio = media("song.opus", 20_000)
        media("notes.txt", 30_000)
        media("partial.mp4.part", 40_000)
        media("cover.jpg", 50_000)
        folder.newFolder("directory.mp4")

        assertEquals(listOf(audio, opened), PlaylistBuilder.build(opened).files)
    }

    @Test fun equalTimestampsHaveStableNameOrder() {
        val second = media("b.mp4", 10_000)
        val first = media("a.mp4", 10_000)

        assertEquals(listOf(first, second), PlaylistBuilder.build(second).files)
        assertEquals(1, PlaylistBuilder.build(second).startIndex)
    }

    @Test fun singleFileStartsAtZero() {
        val opened = media("only.flac", 10_000)

        assertEquals(listOf(opened), PlaylistBuilder.build(opened).files)
        assertEquals(0, PlaylistBuilder.build(opened).startIndex)
    }

    @Test fun explicitlyOpenedUnknownExtensionIsPreserved() {
        val opened = media("opened.unknown", 10_000)
        media("other.unknown", 20_000)

        assertEquals(listOf(opened), PlaylistBuilder.build(opened).files)
        assertEquals(0, PlaylistBuilder.build(opened).startIndex)
    }

    @Test fun missingFileReturnsEmptyPlaylist() {
        val playlist = PlaylistBuilder.build(File(folder.root, "missing.mp4"))

        assertTrue(playlist.files.isEmpty())
        assertEquals(0, playlist.startIndex)
    }
}
