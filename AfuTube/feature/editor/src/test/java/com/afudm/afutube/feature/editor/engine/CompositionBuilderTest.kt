package com.afudm.afutube.feature.editor.engine

import com.afudm.afutube.feature.editor.model.EditorProject
import com.afudm.afutube.feature.editor.model.VideoClip
import org.junit.Assert.assertEquals
import org.junit.Test

class CompositionBuilderTest {
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
}
