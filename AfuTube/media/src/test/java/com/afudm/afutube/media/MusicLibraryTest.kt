package com.afudm.afutube.media

import org.junit.Assert.*
import org.junit.Test

class MusicLibraryTest {
    @Test fun selectsPermissionForAndroidVersion() {
        assertEquals("android.permission.READ_EXTERNAL_STORAGE", musicPermission(24))
        assertEquals("android.permission.READ_EXTERNAL_STORAGE", musicPermission(32))
        assertEquals("android.permission.READ_MEDIA_AUDIO", musicPermission(33))
        assertEquals("android.permission.READ_MEDIA_AUDIO", musicPermission(37))
    }

    @Test fun includesMusicFolderAndDownloadsWithoutMusicFlag() {
        assertTrue(isMusicEntry(false, "Music/Album/"))
        assertTrue(isMusicEntry(false, "/storage/emulated/0/Music/song.mp3"))
        assertTrue(isMusicEntry(false, "Download/afutube/"))
        assertTrue(isMusicEntry(true, "Other/"))
        assertFalse(isMusicEntry(false, "Recordings/"))
        assertFalse(isMusicEntry(false, "Download/afutube-other/"))
    }

    @Test fun listIsSortedDeduplicatedAndKeepsDistinctTracksWithSameTitle() {
        val first = MusicTrack("content://audio/1", "Zulu", "Artist")
        val second = MusicTrack("content://audio/2", "Alpha", "Artist")
        val third = MusicTrack("content://audio/3", "Alpha", "Other")
        assertEquals(listOf(second, third, first), prepareMusicList(listOf(first, second, first, third)))
        assertTrue(prepareMusicList(emptyList()).isEmpty())
    }
}
