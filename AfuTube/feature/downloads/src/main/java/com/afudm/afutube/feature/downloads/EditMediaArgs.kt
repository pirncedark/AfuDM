package com.afudm.afutube.feature.downloads

import java.io.File
import java.util.Locale

internal fun trimOutput(input: File) = File(input.parentFile, "${input.nameWithoutExtension}_kirpik.${input.extension}")
internal fun trimArgs(input: File, output: File, startMs: Long, endMs: Long): List<String> = editArgs(input, output, startMs, endMs, null, 100, 100)
internal fun musicOutput(input: File) = File(input.parentFile, "${input.nameWithoutExtension}_muzikli.mp4")
internal fun muteOutput(input: File) = File(input.parentFile, "${input.nameWithoutExtension}_sessiz.${input.extension}")
internal fun muteArgs(input: File, output: File): List<String> = editArgs(input, output, 0, Long.MAX_VALUE, null, 0, 0)
internal fun audioOutput(input: File) = File(input.parentFile, "${input.nameWithoutExtension}_ses.m4a")
internal fun audioArgs(input: File, output: File): List<String> = listOf("-y", "-i", input.absolutePath, "-vn", "-c:a", "aac", "-b:a", "192k", output.absolutePath)
internal fun addMusicArgs(video: File, music: File, output: File, lowerOriginal: Boolean, hasVideoAudio: Boolean = true): List<String> =
    editArgs(video, output, 0, Long.MAX_VALUE, music, if (lowerOriginal) 20 else 100, 100, hasVideoAudio)

/** Builds one FFmpeg invocation for trim and audio mixing; paths are never overwritten. */
internal fun editArgs(input: File, output: File, startMs: Long, endMs: Long, music: File?, originalVolume: Int, musicVolume: Int, hasVideoAudio: Boolean = true): List<String> {
    require(startMs >= 0 && endMs > startMs)
    require(output.absolutePath != input.absolutePath)
    require(originalVolume in 0..100 && musicVolume in 0..100)
    val args = mutableListOf("-y", "-ss", seconds(startMs), "-i", input.absolutePath)
    music?.let { args += listOf("-i", it.absolutePath) }
    val duration = if (endMs == Long.MAX_VALUE) null else seconds(endMs - startMs)
    if (duration != null) args += listOf("-t", duration)
    if (music == null) {
        if (originalVolume == 0 || !hasVideoAudio) args += listOf("-c:v", "copy", "-an")
        else if (originalVolume == 100) args += listOf("-c:v", "copy", "-c:a", "copy")
        else args += listOf("-filter_complex", "[0:a]volume=${originalVolume / 100.0}[a]", "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac")
    } else {
        val hasOriginal = hasVideoAudio && originalVolume > 0
        val filter = when {
            hasOriginal -> "[0:a]volume=${originalVolume / 100.0}[orig];[1:a]volume=${musicVolume / 100.0}[music];[orig][music]amix=inputs=2:duration=first:dropout_transition=2[a]"
            hasVideoAudio && originalVolume == 0 -> "[1:a]volume=${musicVolume / 100.0}[a]"
            else -> "[1:a]volume=${musicVolume / 100.0}[a]"
        }
        args += listOf("-filter_complex", filter, "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac")
    }
    args += output.absolutePath
    return args
}
private fun seconds(ms: Long) = "%.3f".format(Locale.US, ms.coerceAtLeast(0) / 1000.0)
