package com.afudm.afutube.runtime

import android.content.Context
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Runs the same packaged FFmpeg executable shipped by youtubedl-android. */
object FfmpegRunner {
    suspend fun hasAudio(context: Context, input: File): Boolean {
        val output = mutableListOf<String>()
        run(context, listOf("-hide_banner", "-i", input.absolutePath)) { output += it }
        return output.any { it.contains("Audio:") }
    }

    suspend fun run(context: Context, args: List<String>, onProgress: (String) -> Unit = {}): Int = withContext(Dispatchers.IO) {
        MediaRuntime.ensureInitialized(context.applicationContext)
        val nativeDir = context.applicationInfo.nativeLibraryDir
        val binary = File(nativeDir, "libffmpeg.so")
        check(binary.isFile) { "FFmpeg unavailable" }
        val packages = File(context.noBackupFilesDir, "youtubedl-android/packages")
        val extracted = File(packages, "ffmpeg")
        val process = ProcessBuilder(listOf(binary.absolutePath) + args)
            .redirectErrorStream(true)
            .apply { environment()["LD_LIBRARY_PATH"] = listOf("python", "ffmpeg", "aria2c").joinToString(":") { File(packages, it).absolutePath + "/usr/lib" } }
            .start()
        process.inputStream.bufferedReader().useLines { lines -> lines.forEach(onProgress) }
        process.waitFor()
    }
}
