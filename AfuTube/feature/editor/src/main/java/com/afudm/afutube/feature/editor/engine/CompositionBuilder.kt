package com.afudm.afutube.feature.editor.engine

import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import androidx.media3.transformer.Composition
import androidx.media3.transformer.EditedMediaItem
import androidx.media3.transformer.EditedMediaItemSequence
import androidx.media3.transformer.Transformer
import com.afudm.afutube.feature.editor.model.EditorProject

/** Pure Kotlin description of the timeline. It can be built and tested on the JVM. */
data class CompositionPlan(
    val clips: List<MediaSegment>,
    val musicTracks: List<MediaSegment>
) {
    data class MediaSegment(
        val path: String,
        val trimStartMs: Long,
        val trimEndMs: Long,
        val speed: Double,
        val volume: Double
    )
}

object CompositionPlanBuilder {
    fun build(project: EditorProject): CompositionPlan {
        require(project.clips.isNotEmpty()) { "En az bir video ekle." }
        return CompositionPlan(
            clips = project.clips.map { CompositionPlan.MediaSegment(it.source, it.trimStartMs, it.trimEndMs, it.speed, it.volume) },
            musicTracks = project.musicTracks.map { CompositionPlan.MediaSegment(it.source, it.trimStartMs, it.trimEndMs, 1.0, it.volume) }
        )
    }
}

/** Converts the platform-free plan to Media3 types at the Android boundary. */
@OptIn(UnstableApi::class)
object CompositionBuilder {
    data class Result(val composition: Composition, val clipCount: Int, val trimRangesMs: List<LongRange>)

    fun build(project: EditorProject): Result = build(CompositionPlanBuilder.build(project))

    fun build(plan: CompositionPlan): Result {
        val videoItems = plan.clips.map { it.toEditedMediaItem() }
        val sequences = mutableListOf(EditedMediaItemSequence.withAudioAndVideoFrom(videoItems))
        if (plan.musicTracks.isNotEmpty()) {
            val musicItems = plan.musicTracks.map { it.toEditedMediaItem(removeVideo = true) }
            sequences += EditedMediaItemSequence.withAudioFrom(musicItems).buildUpon().setIsLooping(false).build()
        }
        return Result(
            Composition.Builder(sequences).build(),
            videoItems.size,
            plan.clips.map { it.trimStartMs..it.trimEndMs }
        )
    }

    private fun CompositionPlan.MediaSegment.toEditedMediaItem(removeVideo: Boolean = false): EditedMediaItem {
        val mediaItem = MediaItem.Builder()
            .setUri(path)
            .setClippingConfiguration(
                MediaItem.ClippingConfiguration.Builder()
                    .setStartPositionMs(trimStartMs)
                    .setEndPositionMs(trimEndMs)
                    .build()
            )
            .build()
        val builder = EditedMediaItem.Builder(mediaItem)
            .setDurationUs((trimEndMs - trimStartMs) * 1_000L)
            .setFrameRate(30)
        if (removeVideo) builder.setRemoveVideo(true)
        return builder.build()
    }

    /** Export entry point deliberately accepts the same Composition built for preview. */
    fun startExport(transformer: Transformer, result: Result, outputPath: String) {
        transformer.start(result.composition, outputPath)
    }
}
