package com.afudm.afutube.feature.editor.engine

/** Export options and helpers kept free of Android types for JVM tests. */
enum class ExportQuality { SOURCE, P1080, P720, P480 }

data class ExportSize(val width: Int, val height: Int)

fun exportSize(sourceWidth: Int, sourceHeight: Int, quality: ExportQuality): ExportSize {
    require(sourceWidth > 0 && sourceHeight > 0)
    val cap = when (quality) {
        ExportQuality.SOURCE -> Int.MAX_VALUE
        ExportQuality.P1080 -> 1920
        ExportQuality.P720 -> 1280
        ExportQuality.P480 -> 854
    }
    val longSide = maxOf(sourceWidth, sourceHeight)
    val scale = minOf(1.0, cap.toDouble() / longSide)
    return ExportSize((sourceWidth * scale).toInt().coerceAtLeast(1), (sourceHeight * scale).toInt().coerceAtLeast(1))
}

fun exportFileName(sourceName: String, existingNames: List<String> = emptyList()): String {
    val stem = sourceName.substringBeforeLast('.', sourceName)
        .replace(Regex("[^A-Za-z0-9_-]+"), "_").trim('_', '-').ifBlank { "video" }
    val base = "${stem}_edit"
    if ("$base.mp4" !in existingNames) return "$base.mp4"
    var suffix = 1
    while ("$base ($suffix).mp4" in existingNames) suffix++
    return "$base ($suffix).mp4"
}

fun exportProgress(progress: Int): Int = progress.coerceIn(0, 99)
