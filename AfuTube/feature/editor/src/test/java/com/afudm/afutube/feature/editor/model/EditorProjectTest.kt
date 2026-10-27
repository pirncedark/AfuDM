package com.afudm.afutube.feature.editor.model

import org.junit.Assert.*
import org.junit.Test

class EditorProjectTest {
    @Test fun audioFieldsSurviveJsonRoundTrip() {
        val project = EditorProject(
            clips = listOf(VideoClip("clip", "video.mp4", 10_000, speed = 1.5, volume = 2.0, originalAudioEnabled = false, fadeInMs = 500, fadeOutMs = 700)),
            musicTracks = listOf(MusicTrack("music", "song.mp3", startMs = 300, trimEndMs = 8_000, volume = 0.65, fadeInMs = 400, fadeOutMs = 600)),
            dialogueDucking = true
        )
        assertEquals(project, EditorProject.fromJson(project.toJson()))
    }

    private fun project() = EditorProject(clips = listOf(VideoClip("a", "file://a", 10_000), VideoClip("b", "file://b", 8_000)))

    @Test fun splitCreatesAdjacentSourceRanges() {
        val split = project().splitClip(0, 4_000)
        assertEquals(3, split.clips.size)
        assertEquals(4_000, split.clips[0].trimEndMs)
        assertEquals(4_000, split.clips[1].trimStartMs)
    }
    @Test fun removeAndReorderChangeOnlyRequestedClip() {
        assertEquals(listOf("b"), project().removeClip(0).clips.map { it.id })
        assertEquals(listOf("b", "a"), project().reorderClip(0, 1).clips.map { it.id })
    }
    @Test fun trimAcceptsValidRangeAndRejectsOutOfBounds() {
        assertEquals(2_000, project().trimClip(0, 2_000, 8_000).clips[0].trimStartMs)
        assertThrows(IllegalArgumentException::class.java) { project().trimClip(0, 0, 10_001) }
    }
    @Test fun jsonRoundTripsEveryProjectFieldAndEscapesText() {
        val value = EditorProject(project().clips.mapIndexed { i, clip -> if (i == 0) clip.copy(minimumDurationMs = 250) else clip }, listOf(MusicTrack("m", "music.mp3", trimEndMs = 20_000, volume = .7)), listOf(TextOverlay("t", "hi \"there\"", 10, 200)), EditorFilter.WARM, AspectRatio.SQUARE_1_1)
        assertEquals(value, EditorProject.fromJson(value.toJson()))
    }
}
