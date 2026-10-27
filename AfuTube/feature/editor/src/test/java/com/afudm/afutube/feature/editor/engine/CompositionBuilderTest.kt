package com.afudm.afutube.feature.editor.engine

import com.afudm.afutube.feature.editor.model.EditorProject
import com.afudm.afutube.feature.editor.model.VideoClip
import com.afudm.afutube.feature.editor.model.MusicTrack
import org.junit.Assert.assertEquals
import org.junit.Test

class CompositionBuilderTest {
    @Test fun gainEnvelopeCoversFadesBoostAndMutedAudio() {
        assertEquals(0.0, gainAt(0, 1_000, 1.0, 200, 200), 0.0)
        assertEquals(0.5, gainAt(100, 1_000, 1.0, 200, 200), 0.0001)
        assertEquals(1.0, gainAt(800, 1_000, 1.0, 200, 200), 0.0001)
        assertEquals(0.5, gainAt(900, 1_000, 1.0, 200, 200), 0.0001)
        assertEquals(0.0, gainAt(1_000, 1_000, 1.0, 200, 200), 0.0)
        assertEquals(2.0, gainAt(500, 1_000, 2.0, 0, 0), 0.0)
        assertEquals(0.0, gainAt(500, 1_000, 0.0, 0, 0), 0.0)
    }

    @Test fun buildsOnePlanItemPerClipWithTrimRangesAndAudioSettings() {
        val project = EditorProject(clips = listOf(
            VideoClip("a", "file:///a.mp4", 10_000, 1_250, 5_750, speed = 1.5, volume = 0.75),
            VideoClip("b", "file:///b.mp4", 8_000, 500, 4_500)
        ))
        val plan = CompositionPlanBuilder.build(project)
        assertEquals(2, plan.clips.size)
        assertEquals(listOf("file:///a.mp4", "file:///b.mp4"), plan.clips.map { it.path })
        assertEquals(listOf(1_250L..5_750L, 500L..4_500L), plan.clips.map { it.trimStartMs..it.trimEndMs })
        assertEquals(listOf(1.5, 1.0), plan.clips.map { it.speed })
        assertEquals(listOf(0.75, 1.0), plan.clips.map { it.volume })
    }

    @Test fun buildsSpeedPlanAndDucksMusicToThirtyPercent() {
        val project = EditorProject(
            clips = listOf(VideoClip("v", "video.mp4", 8_000, speed = 2.0)),
            musicTracks = listOf(MusicTrack("m", "music.mp3", startMs = 1_250, trimEndMs = 5_000, volume = 0.8)),
            dialogueDucking = true
        )
        val plan = CompositionPlanBuilder.build(project)
        assertEquals(2.0, plan.clips.single().speed, 0.0)
        assertEquals(1_250L, plan.musicTracks.single().startMs)
        assertEquals(0.24, plan.musicTracks.single().volume, 0.0001)
    }
}
