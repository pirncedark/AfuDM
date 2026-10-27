package com.afudm.afutube.feature.editor.engine

import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import androidx.media3.transformer.Composition
import androidx.media3.transformer.EditedMediaItem
import androidx.media3.transformer.EditedMediaItemSequence
import androidx.media3.transformer.Transformer
import com.afudm.afutube.feature.editor.model.EditorProject

/** Produces the single composition shared by CompositionPlayer preview and Transformer export. */
@OptIn(UnstableApi::class)
object CompositionBuilder {
    data class Result(val composition: Composition, val clipCount: Int, val trimRangesMs: List<LongRange>)

    fun build(project: EditorProject): Result {
        require(project.clips.isNotEmpty()) { "En az bir video ekle." }
        val videoItems = project.clips.map { clip ->
            val durationMs = clip.trimEndMs - clip.trimStartMs
            val mediaItem = MediaItem.Builder()
                .setUri(clip.source)
                .setClippingConfiguration(
                    MediaItem.ClippingConfiguration.Builder()
                        .setStartPositionMs(clip.trimStartMs)
                        .setEndPositionMs(clip.trimEndMs)
                        .build()
                )
                .build()
            EditedMediaItem.Builder(mediaItem)
                .setDurationUs(durationMs * 1_000L)
                .setFrameRate(30)
                .build()
        }
        val sequences = mutableListOf(EditedMediaItemSequence.withAudioAndVideoFrom(videoItems))
        if (project.musicTracks.isNotEmpty()) {
            val musicItems = project.musicTracks.map { track ->
                val durationMs = track.trimEndMs - track.trimStartMs
                val item = MediaItem.Builder().setUri(track.source)
                    .setClippingConfiguration(MediaItem.ClippingConfiguration.Builder()
                        .setStartPositionMs(track.trimStartMs).setEndPositionMs(track.trimEndMs).build())
                    .build()
                EditedMediaItem.Builder(item).setDurationUs(durationMs * 1_000L)
                    .setFrameRate(30).setRemoveVideo(true).build()
            }
            sequences += EditedMediaItemSequence.withAudioFrom(musicItems).buildUpon().setIsLooping(false).build()
        }
        val composition = Composition.Builder(sequences).build()
        return Result(composition, videoItems.size, project.clips.map { it.trimStartMs..it.trimEndMs })
    }

    /** Export entry point deliberately accepts the same Composition built for preview. */
    fun startExport(transformer: Transformer, result: Result, outputPath: String) {
        transformer.start(result.composition, outputPath)
    }
}
