package com.afudm.afutube.media

import java.io.File

internal data class Playlist(val files: List<File>, val startIndex: Int)

internal object PlaylistBuilder {
    // The detector defaults unknown extensions to VIDEO; restrict that fallback
    // so images, subtitles and unfinished downloads never enter the queue.
    private val videoExtensions = setOf("mp4", "mkv", "webm", "mov", "avi", "m4v", "3gp", "ts")

    fun build(opened: File): Playlist {
        if (!opened.isFile) return Playlist(emptyList(), 0)
        val siblings = opened.parentFile?.listFiles().orEmpty().filter { file ->
            file.isFile && (MediaFileTypeDetector.fromPath(file.path) == MediaFileType.AUDIO ||
                file.extension.lowercase() in videoExtensions)
        }
        // Preserve an explicitly opened file even if its extension is unknown.
        val files = (siblings + opened).distinctBy { it.absolutePath }
            .sortedWith(compareByDescending<File> { it.lastModified() }.thenBy { it.name })
        return Playlist(files, files.indexOfFirst { it.absolutePath == opened.absolutePath })
    }
}
