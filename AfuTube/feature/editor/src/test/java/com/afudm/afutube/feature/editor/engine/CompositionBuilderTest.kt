package com.afudm.afutube.feature.editor.engine

import com.afudm.afutube.feature.editor.model.EditorProject
import com.afudm.afutube.feature.editor.model.VideoClip
import androidx.media3.common.util.UnstableApi
import org.junit.Assert.assertEquals
import org.junit.Test

@OptIn(UnstableApi::class)
class CompositionBuilderTest {
    @Test fun buildsOneSequenceItemPerClipWithTrimRangesInMilliseconds() {
        val project = EditorProject(clips = listOf(
            VideoClip("a", "file:///a.mp4", 10_000, 1_250, 5_750),
            VideoClip("b", "file:///b.mp4", 8_000, 500, 4_500)
        ))
        val built = CompositionBuilder.build(project)
        assertEquals(2, built.clipCount)
        assertEquals(listOf(1_250L..5_750L, 500L..4_500L), built.trimRangesMs)
        assertEquals(2, built.composition.sequences.first().editedMediaItems.size)
    }
}
