package com.afudm.afutube.feature.editor.engine

import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import androidx.media3.transformer.Composition
import androidx.media3.transformer.EditedMediaItem
import androidx.media3.transformer.EditedMediaItemSequence
import androidx.media3.transformer.Transformer
import androidx.media3.common.audio.AudioProcessor
import androidx.media3.common.audio.SonicAudioProcessor
import androidx.media3.common.audio.BaseAudioProcessor
import androidx.media3.common.C
import java.nio.ByteBuffer
import java.nio.ByteOrder
import androidx.media3.effect.SpeedChangeEffect
import androidx.media3.transformer.Effects
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
        val volume: Double,
        val originalAudioEnabled: Boolean = true,
        val fadeInMs: Long = 0,
        val fadeOutMs: Long = 0,
        val startMs: Long = 0
    )
}

object CompositionPlanBuilder {
    fun build(project: EditorProject): CompositionPlan {
        require(project.clips.isNotEmpty()) { "En az bir video ekle." }
        return CompositionPlan(
            clips = project.clips.map { CompositionPlan.MediaSegment(it.source, it.trimStartMs, it.trimEndMs, it.speed, if (it.originalAudioEnabled) it.volume else 0.0, it.originalAudioEnabled, it.fadeInMs, it.fadeOutMs) },
            musicTracks = project.musicTracks.map { MusicTrack -> CompositionPlan.MediaSegment(MusicTrack.source, MusicTrack.trimStartMs, MusicTrack.trimEndMs, 1.0, MusicTrack.volume * if (project.dialogueDucking) .3 else 1.0, true, MusicTrack.fadeInMs, MusicTrack.fadeOutMs, MusicTrack.startMs) }
        )
    }
}

/** Linear gain envelope shared by clip and music audio. Time is relative to the trimmed segment. */
fun gainAt(positionMs: Long, durationMs: Long, volume: Double, fadeInMs: Long, fadeOutMs: Long): Double {
    if (durationMs <= 0 || positionMs < 0 || positionMs >= durationMs || volume <= 0.0) return 0.0
    val fadeIn = if (fadeInMs > 0) (positionMs.toDouble() / fadeInMs).coerceIn(0.0, 1.0) else 1.0
    val fadeOut = if (fadeOutMs > 0) ((durationMs - positionMs).toDouble() / fadeOutMs).coerceIn(0.0, 1.0) else 1.0
    return volume * minOf(fadeIn, fadeOut)
}

/** Applies volume and fades to PCM samples. Supports Media3 float and 16-bit PCM output. */
@OptIn(UnstableApi::class)
class GainFadeAudioProcessor(
    private val volume: Double,
    private val durationMs: Long,
    private val fadeInMs: Long,
    private val fadeOutMs: Long
) : BaseAudioProcessor() {
    private var framesProcessed = 0L
    private var sampleRate = 0
    private var channels = 0

    override fun onConfigure(inputAudioFormat: AudioProcessor.AudioFormat): AudioProcessor.AudioFormat {
        require(inputAudioFormat.encoding == C.ENCODING_PCM_FLOAT || inputAudioFormat.encoding == C.ENCODING_PCM_16BIT) {
            "GainFadeAudioProcessor requires float or 16-bit PCM"
        }
        sampleRate = inputAudioFormat.sampleRate
        channels = inputAudioFormat.channelCount
        return inputAudioFormat
    }

    override fun onFlush() { framesProcessed = 0L }

    override fun queueInput(inputBuffer: ByteBuffer) {
        val bytesPerSample = if (inputAudioFormat.encoding == C.ENCODING_PCM_FLOAT) 4 else 2
        val sampleCount = inputBuffer.remaining() / bytesPerSample
        val output = replaceOutputBuffer(sampleCount * bytesPerSample).order(ByteOrder.nativeOrder())
        repeat(sampleCount) {
            val frame = framesProcessed / channels
            val positionMs = if (sampleRate > 0) frame * 1_000L / sampleRate else durationMs
            val gain = gainAt(positionMs, durationMs, volume, fadeInMs, fadeOutMs).toFloat()
            if (inputAudioFormat.encoding == C.ENCODING_PCM_FLOAT) {
                output.putFloat(inputBuffer.getFloat() * gain)
            } else {
                val value = inputBuffer.short * gain
                output.putShort(value.toInt().coerceIn(Short.MIN_VALUE.toInt(), Short.MAX_VALUE.toInt()).toShort())
            }
            framesProcessed++
        }
        output.flip()
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
        val processors = mutableListOf<AudioProcessor>()
        processors += GainFadeAudioProcessor(volume, trimEndMs - trimStartMs, fadeInMs, fadeOutMs)
        processors += SonicAudioProcessor().apply { setSpeed(speed.toFloat()) }
        val effects = listOf(SpeedChangeEffect(speed.toFloat()))
        val builder = EditedMediaItem.Builder(mediaItem)
            .setDurationUs((trimEndMs - trimStartMs) * 1_000L)
            .setFrameRate(30)
            .setEffects(Effects(processors, effects))
        if (removeVideo) builder.setRemoveVideo(true)
        return builder.build()
    }

    /** Export entry point deliberately accepts the same Composition built for preview. */
    fun startExport(transformer: Transformer, result: Result, outputPath: String) {
        transformer.start(result.composition, outputPath)
    }
}
