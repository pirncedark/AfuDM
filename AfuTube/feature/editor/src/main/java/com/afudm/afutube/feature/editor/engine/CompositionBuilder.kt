package com.afudm.afutube.feature.editor.engine

import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import androidx.media3.transformer.Composition
import androidx.media3.transformer.EditedMediaItem
import androidx.media3.transformer.EditedMediaItemSequence
import androidx.media3.transformer.Transformer
import androidx.media3.common.audio.AudioProcessor
import androidx.media3.common.audio.BaseAudioProcessor
import androidx.media3.common.C
import java.nio.ByteBuffer
import java.nio.ByteOrder
import androidx.media3.effect.RgbFilter
import androidx.media3.effect.RgbMatrix
import androidx.media3.effect.Brightness
import androidx.media3.effect.Contrast
import androidx.media3.effect.Presentation
import androidx.media3.effect.OverlayEffect
import androidx.media3.effect.TextOverlay as MediaTextOverlay
import androidx.media3.effect.StaticOverlaySettings
import androidx.media3.effect.TextureOverlay
import android.text.SpannableString
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.text.style.RelativeSizeSpan
import android.graphics.Color as AndroidColor
import androidx.media3.transformer.Effects
import com.afudm.afutube.feature.editor.model.EditorProject
import com.afudm.afutube.feature.editor.model.EditorFilter
import com.afudm.afutube.feature.editor.model.AspectRatio
import com.afudm.afutube.feature.editor.model.TextOverlay

/** Pure Kotlin description of the timeline. It can be built and tested on the JVM. */
data class CompositionPlan(
    val clips: List<MediaSegment>,
    val musicTracks: List<MediaSegment>,
    val textOverlays: List<TextOverlay> = emptyList(),
    val filter: EditorFilter = EditorFilter.NONE,
    val brightness: Double = 0.0,
    val contrast: Double = 0.0,
    val aspectRatio: AspectRatio = AspectRatio.ORIGINAL,
    val outputSize: OutputSize = OutputSize(1920, 1080),
    val filterMatrix: List<Float> = FilterMatrices.forFilter(filter)
) {
    data class OutputSize(val width: Int, val height: Int)
    data class MediaSegment(
        val path: String,
        val trimStartMs: Long,
        val trimEndMs: Long,
        val speed: Double,
        val volume: Double,
        val originalAudioEnabled: Boolean = true,
        val fadeInMs: Long = 0,
        val fadeOutMs: Long = 0,
        val startMs: Long = 0,
        /** Full source length; Media3 needs it (not the trimmed length) to apply clipping. */
        val sourceDurationMs: Long = trimEndMs
    )
}

object CompositionPlanBuilder {
    fun build(project: EditorProject, sourceWidth: Int = 1920, sourceHeight: Int = 1080): CompositionPlan {
        require(project.clips.isNotEmpty()) { "En az bir video ekle." }
        return CompositionPlan(
            clips = project.clips.map { CompositionPlan.MediaSegment(it.source, it.trimStartMs, it.trimEndMs, it.speed, if (it.originalAudioEnabled) it.volume else 0.0, it.originalAudioEnabled, it.fadeInMs, it.fadeOutMs, sourceDurationMs = it.sourceDurationMs) },
            musicTracks = project.musicTracks.map { m -> CompositionPlan.MediaSegment(m.source, m.trimStartMs, m.trimEndMs, 1.0, m.volume * if (project.dialogueDucking) .3 else 1.0, true, m.fadeInMs, m.fadeOutMs, m.startMs) },
            textOverlays = project.textOverlays, filter = project.filter, brightness = project.brightness,
            contrast = project.contrast, aspectRatio = project.aspectRatio,
            outputSize = aspectSize(project.aspectRatio, sourceWidth, sourceHeight)
        )
    }
}

fun aspectSize(ratio: AspectRatio, width: Int, height: Int): CompositionPlan.OutputSize {
    require(width > 0 && height > 0)
    val target = when (ratio) { AspectRatio.ORIGINAL -> width.toDouble()/height; AspectRatio.PORTRAIT_9_16 -> 9.0/16; AspectRatio.SQUARE_1_1 -> 1.0; AspectRatio.LANDSCAPE_16_9 -> 16.0/9 }
    if (ratio == AspectRatio.ORIGINAL) return CompositionPlan.OutputSize(width, height)
    val longSide = maxOf(width, height)
    return if (target < 1.0) CompositionPlan.OutputSize((longSide*target).toInt(), longSide) else CompositionPlan.OutputSize(longSide, (longSide/target).toInt())
}

object FilterMatrices {
    fun forFilter(filter: EditorFilter): List<Float> = when(filter) {
        EditorFilter.NONE -> listOf(1f,0f,0f,0f, 0f,1f,0f,0f, 0f,0f,1f,0f, 0f,0f,0f,1f)
        EditorFilter.BLACK_WHITE -> listOf(.2126f,.7152f,.0722f,0f, .2126f,.7152f,.0722f,0f, .2126f,.7152f,.0722f,0f, 0f,0f,0f,1f)
        EditorFilter.WARM -> listOf(1.08f,0f,0f,0f, 0f,1f,0f,0f, 0f,0f,.9f,0f, 0f,0f,0f,1f)
        EditorFilter.COOL -> listOf(.9f,0f,0f,0f, 0f,1f,0f,0f, 0f,0f,1.08f,0f, 0f,0f,0f,1f)
        EditorFilter.VIVID -> listOf(1.15f,0f,0f,0f, 0f,1.15f,0f,0f, 0f,0f,1.15f,0f, 0f,0f,0f,1f)
    }
}

private class MatrixRgbFilter(private val values: List<Float>) : RgbMatrix {
    override fun getMatrix(presentationTimeUs: Long, useHdr: Boolean): FloatArray = values.toFloatArray()
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

    fun build(project: EditorProject, outputSize: CompositionPlan.OutputSize): Result =
        build(CompositionPlanBuilder.build(project), outputSize)

    fun build(plan: CompositionPlan): Result = build(plan, null)

    private fun build(plan: CompositionPlan, outputSize: CompositionPlan.OutputSize?): Result {
        val ratio = when(plan.aspectRatio) { AspectRatio.ORIGINAL -> null; AspectRatio.PORTRAIT_9_16 -> 9f/16f; AspectRatio.SQUARE_1_1 -> 1f; AspectRatio.LANDSCAPE_16_9 -> 16f/9f }
        val visualEffects = buildList<androidx.media3.common.Effect> {
            if (ratio != null) add(Presentation.createForAspectRatio(ratio, Presentation.LAYOUT_SCALE_TO_FIT))
            outputSize?.let { add(Presentation.createForWidthAndHeight(it.width, it.height, Presentation.LAYOUT_SCALE_TO_FIT)) }
            when(plan.filter) {
                EditorFilter.NONE -> Unit
                EditorFilter.BLACK_WHITE -> add(RgbFilter.createGrayscaleFilter())
                EditorFilter.WARM -> add(MatrixRgbFilter(plan.filterMatrix))
                EditorFilter.COOL -> add(MatrixRgbFilter(plan.filterMatrix))
                EditorFilter.VIVID -> add(MatrixRgbFilter(plan.filterMatrix))
            }
            if (plan.brightness != 0.0) add(Brightness(plan.brightness.toFloat()))
            if (plan.contrast != 0.0) add(Contrast(plan.contrast.toFloat()))
        }
        var timelineOffsetMs = 0L
        val videoItems = plan.clips.map { clip ->
            val durationMs = ((clip.trimEndMs - clip.trimStartMs) / clip.speed).toLong()
            val clipEndMs = timelineOffsetMs + durationMs
            val clipTexts = plan.textOverlays.mapNotNull { text ->
                val start = maxOf(text.startMs, timelineOffsetMs)
                val end = minOf(text.endMs, clipEndMs)
                if (end <= start) null else text.copy(startMs = start - timelineOffsetMs, endMs = end - timelineOffsetMs)
            }
            val clipEffects = visualEffects + if (clipTexts.isEmpty()) emptyList() else listOf(OverlayEffect(clipTexts.map { it.toMediaOverlay() }))
            timelineOffsetMs = clipEndMs
            clip.toEditedMediaItem(videoEffects = clipEffects)
        }
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

    private fun CompositionPlan.MediaSegment.toEditedMediaItem(removeVideo: Boolean = false, videoEffects: List<androidx.media3.common.Effect> = emptyList()): EditedMediaItem {
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
        val effects = emptyList<androidx.media3.common.Effect>()
        val builder = EditedMediaItem.Builder(mediaItem)
            .setDurationUs(sourceDurationMs * 1_000L)
            .setFrameRate(30)
            .setEffects(Effects(processors, if (removeVideo) effects else effects + videoEffects))
        // CompositionPlayer only supports speed set on the item itself (not SpeedChangeEffect).
        if (speed != 1.0) builder.setSpeed(ConstantSpeed(speed.toFloat()))
        if (removeVideo) builder.setRemoveVideo(true)
        return builder.build()
    }

    private fun TextOverlay.toMediaOverlay(): TextureOverlay {
        val label = this
        val text = SpannableString(label.text).apply { setSpan(ForegroundColorSpan(AndroidColor.parseColor(label.color)), 0, length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE); setSpan(RelativeSizeSpan(label.sizeSp / 100f), 0, length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE) }
        val settings = StaticOverlaySettings.Builder().setOverlayFrameAnchor((label.x * 2 - 1).toFloat(), (1 - label.y * 2).toFloat()).setBackgroundFrameAnchor(0f, 0f).build()
        return object : MediaTextOverlay() {
            override fun getText(presentationTimeUs: Long): SpannableString = if (label.isVisibleAt(presentationTimeUs / 1_000L)) text else SpannableString("")
            override fun getOverlaySettings(presentationTimeUs: Long) = settings
        }
    }

    /** Export entry point deliberately accepts the same Composition built for preview. */
    fun startExport(transformer: Transformer, result: Result, outputPath: String) {
        transformer.start(result.composition, outputPath)
    }
}

private class ConstantSpeed(private val speed: Float) : androidx.media3.common.audio.SpeedProvider {
    override fun getSpeed(timeUs: Long): Float = speed
    override fun getNextSpeedChangeTimeUs(timeUs: Long): Long = androidx.media3.common.C.TIME_UNSET
}
