package com.afudm.afutube.runtime

import com.afudm.afutube.core.extractor.UrlNormalizer

data class MediaRuntimeHealth(
    val healthy: Boolean,
    val requiresExtractorUpdate: Boolean,
    val details: String
)

object MediaRuntimeHealthChecker {
    private const val MIN_SUPPORTED_YEAR = 2024

    fun check(ytDlpVersion: String?): MediaRuntimeHealth {
        val version = ytDlpVersion?.trim().orEmpty()
        val normalized = UrlNormalizer.normalize("https://youtu.be/health-check")
        val youtubeUrlMatches = normalized?.startsWith("https://www.youtube.com/watch?v=") == true
        val missing = version.isBlank() || version.equals("bilinmiyor", ignoreCase = true)
        val criticalOld = versionYear(version)?.let { it < MIN_SUPPORTED_YEAR } == true
        val requiresUpdate = missing || criticalOld
        val healthy = !requiresUpdate && youtubeUrlMatches
        val details = "Python / yt-dlp / FFmpeg / aria2 başlatıldı; URL eşleştirme: " +
            if (youtubeUrlMatches) "başarılı" else "başarısız"
        return MediaRuntimeHealth(healthy, requiresUpdate, details)
    }

    private fun versionYear(version: String): Int? =
        Regex("^(\\d{4})").find(version)?.groupValues?.get(1)?.toIntOrNull()
}
