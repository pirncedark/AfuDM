package com.afudm.afutube.feature.editor.model

/** Timeline calculations kept independent of Android and Compose. */
object TimelineMath {
    data class ClipPosition(val index: Int, val sourcePositionMs: Long)

    fun clipAtPlayhead(clips: List<VideoClip>, playheadMs: Long): ClipPosition? {
        var cursor = 0L
        clips.forEachIndexed { index, clip ->
            val duration = ((clip.trimEndMs - clip.trimStartMs) / clip.speed).toLong()
            if (playheadMs < cursor + duration || index == clips.lastIndex) {
                val within = (playheadMs - cursor).coerceIn(0L, duration)
                return ClipPosition(index, (clip.trimStartMs + (within * clip.speed).toLong())
                    .coerceIn(clip.trimStartMs, clip.trimEndMs))
            }
            cursor += duration
        }
        return null
    }

    fun splitOffset(clip: VideoClip, sourcePositionMs: Long): Long? =
        (sourcePositionMs - clip.trimStartMs).takeIf { it >= clip.minimumDurationMs && it <= clip.trimEndMs - clip.trimStartMs - clip.minimumDurationMs }

    fun splitAtPlayhead(project: EditorProject, playheadMs: Long): EditorProject {
        val position = clipAtPlayhead(project.clips, playheadMs) ?: return project
        val offset = splitOffset(project.clips[position.index], position.sourcePositionMs) ?: return project
        return project.splitClip(position.index, offset)
    }

    fun pixelsPerMillisecond(viewportWidthPx: Float, durationMs: Long, zoom: Float): Float =
        (viewportWidthPx.coerceAtLeast(1f) / durationMs.coerceAtLeast(1L) * zoom.coerceIn(.25f, 8f))

    fun rms(samples: ShortArray, bucketSize: Int): List<Float> {
        if (samples.isEmpty() || bucketSize <= 0) return emptyList()
        return samples.asList().chunked(bucketSize).map { bucket ->
            kotlin.math.sqrt(bucket.sumOf { val normalized = it / 32768.0; normalized * normalized } / bucket.size).toFloat()
        }
    }

    fun rmsBuckets(samples: ShortArray, bucketCount: Int): List<Float> {
        if (bucketCount <= 0) return emptyList()
        if (samples.isEmpty()) return List(bucketCount) { 0f }
        return List(bucketCount) { bucket ->
            val from = (bucket.toLong() * samples.size / bucketCount).toInt()
            val until = (((bucket + 1L) * samples.size / bucketCount).toInt()).coerceAtLeast(from + 1).coerceAtMost(samples.size)
            var sum = 0.0
            for (i in from until until) { val sample = samples[i] / 32768.0; sum += sample * sample }
            kotlin.math.sqrt(sum / (until - from)).toFloat()
        }
    }
}
