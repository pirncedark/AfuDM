package com.afudm.afutube.media

import android.content.Context
import android.media.MediaMetadataRetriever
import android.net.Uri
import java.io.File

enum class MediaFileType { AUDIO, VIDEO }

object MediaFileTypeDetector {
    private val audioExtensions = setOf("mp3", "m4a", "opus", "aac", "flac", "wav", "ogg", "weba")
    private val videoExtensions = setOf("mp4", "mkv", "webm", "mov", "avi", "m4v", "3gp", "ts")

    fun fromPath(path: String, context: Context? = null): MediaFileType {
        val ext = File(path).extension.lowercase()
        if (ext in audioExtensions) return MediaFileType.AUDIO
        if (ext in videoExtensions && ext != "webm") return MediaFileType.VIDEO
        if (context != null) {
            val retriever = MediaMetadataRetriever()
            try {
                retriever.setDataSource(context, Uri.fromFile(File(path)))
                val hasVideo = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_HAS_VIDEO)
                if (hasVideo.equals("yes", ignoreCase = true)) return MediaFileType.VIDEO
                if (retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_HAS_AUDIO) != null) return MediaFileType.AUDIO
            } catch (_: Exception) {
            } finally {
                runCatching { retriever.release() }
            }
        }
        return MediaFileType.VIDEO
    }
}
