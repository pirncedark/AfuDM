package com.afudm.afutube.feature.downloads

import java.io.File

internal fun trimOutput(input: File) = File(input.parentFile, "${input.nameWithoutExtension}_kirpik.${input.extension}")
internal fun trimArgs(input: File, output: File, startMs: Long, endMs: Long): List<String> {
    require(startMs >= 0 && endMs > startMs)
    return listOf("-y", "-ss", seconds(startMs), "-to", seconds(endMs), "-i", input.absolutePath, "-c", "copy", output.absolutePath)
}
internal fun musicOutput(input: File) = File(input.parentFile, "${input.nameWithoutExtension}_muzikli.mp4")
internal fun muteOutput(input: File) = File(input.parentFile, "${input.nameWithoutExtension}_sessiz.${input.extension}")
internal fun muteArgs(input: File, output: File): List<String> =
    listOf("-y", "-i", input.absolutePath, "-c", "copy", "-an", output.absolutePath)
internal fun audioOutput(input: File) = File(input.parentFile, "${input.nameWithoutExtension}_ses.m4a")
internal fun audioArgs(input: File, output: File): List<String> =
    listOf("-y", "-i", input.absolutePath, "-vn", "-c:a", "aac", "-b:a", "192k", output.absolutePath)
internal fun addMusicArgs(video: File, music: File, output: File, lowerOriginal: Boolean, hasVideoAudio: Boolean = true): List<String> {
    val args = mutableListOf("-y", "-i", video.absolutePath, "-i", music.absolutePath)
    if (!hasVideoAudio) args += listOf("-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-shortest", "-c:a", "aac")
    else {
        args += listOf("-filter_complex", if (lowerOriginal) "[0:a]volume=0.2[a0];[a0][1:a]amix=inputs=2:duration=first:dropout_transition=2[a]" else "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-shortest", "-c:a", "aac")
    }
    args += output.absolutePath
    return args
}
private fun seconds(ms: Long) = "%.3f".format(java.util.Locale.US, ms / 1000.0)
