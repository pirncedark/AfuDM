package com.afudm.afutube.feature.editor.model

/** Serializable editor state represented using only Kotlin/JVM types. Times are milliseconds. */
data class EditorProject(
    val clips: List<VideoClip> = emptyList(),
    val musicTracks: List<MusicTrack> = emptyList(),
    val textOverlays: List<TextOverlay> = emptyList(),
    val filter: EditorFilter = EditorFilter.NONE,
    val aspectRatio: AspectRatio = AspectRatio.ORIGINAL,
    val dialogueDucking: Boolean = false,
    val brightness: Double = 0.0,
    val contrast: Double = 0.0
) {
    init { require(brightness in -1.0..1.0 && contrast in -1.0..1.0) }
    fun addText(text: TextOverlay) = copy(textOverlays = textOverlays + text)
    fun updateText(id: String, transform: (TextOverlay) -> TextOverlay) = copy(textOverlays = textOverlays.map { if (it.id == id) transform(it) else it })
    fun removeText(id: String) = copy(textOverlays = textOverlays.filterNot { it.id == id })

    fun splitClip(index: Int, atMs: Long): EditorProject {
        val clip = clips[index]
        val sourceAt = clip.trimStartMs + atMs
        require(atMs > 0 && sourceAt < clip.trimEndMs) { "Split point must be inside the clip" }
        return copy(clips = clips.toMutableList().apply {
            removeAt(index)
            addAll(index, listOf(clip.copy(trimEndMs = sourceAt), clip.copy(id = "${clip.id}-split-${sourceAt}", trimStartMs = sourceAt)))
        })
    }

    fun removeClip(index: Int) = copy(clips = clips.toMutableList().apply { removeAt(index) })
    fun reorderClip(from: Int, to: Int): EditorProject {
        require(from in clips.indices && to in clips.indices)
        return copy(clips = clips.toMutableList().apply { add(to, removeAt(from)) })
    }
    fun trimClip(index: Int, startMs: Long, endMs: Long): EditorProject {
        val clip = clips[index]
        require(startMs >= 0 && endMs > startMs && endMs - startMs >= clip.minimumDurationMs)
        require(endMs <= clip.sourceDurationMs)
        return copy(clips = clips.toMutableList().apply { this[index] = clip.copy(trimStartMs = startMs, trimEndMs = endMs) })
    }

    fun toJson(): String = buildString {
        append("{\"version\":1,\"filter\":").quoted(filter.name)
        append(",\"aspectRatio\":").quoted(aspectRatio.name)
        append(",\"brightness\":$brightness,\"contrast\":$contrast")
        append(",\"clips\":[")
        clips.forEachIndexed { i, c -> if (i > 0) append(','); append("{\"id\":").quoted(c.id); append(",\"source\":").quoted(c.source); append(",\"sourceDurationMs\":${c.sourceDurationMs},\"trimStartMs\":${c.trimStartMs},\"trimEndMs\":${c.trimEndMs},\"speed\":${c.speed},\"volume\":${c.volume},\"originalAudioEnabled\":${c.originalAudioEnabled},\"fadeInMs\":${c.fadeInMs},\"fadeOutMs\":${c.fadeOutMs},\"minimumDurationMs\":${c.minimumDurationMs}") ; append('}') }
        append("],\"musicTracks\":[")
        musicTracks.forEachIndexed { i, m -> if (i > 0) append(','); append("{\"id\":").quoted(m.id); append(",\"source\":").quoted(m.source); append(",\"startMs\":${m.startMs},\"trimStartMs\":${m.trimStartMs},\"trimEndMs\":${m.trimEndMs},\"volume\":${m.volume},\"fadeInMs\":${m.fadeInMs},\"fadeOutMs\":${m.fadeOutMs}}") }
        append("],\"textOverlays\":[")
        textOverlays.forEachIndexed { i, t -> if (i > 0) append(','); append("{\"id\":").quoted(t.id); append(",\"text\":").quoted(t.text); append(",\"startMs\":${t.startMs},\"endMs\":${t.endMs},\"color\":").quoted(t.color); append(",\"sizeSp\":${t.sizeSp},\"x\":${t.x},\"y\":${t.y}}") }
        append("],\"dialogueDucking\":$dialogueDucking}")
    }

    companion object {
        /** Parses the stable JSON emitted by [toJson]. Unknown fields are ignored for forward compatibility. */
        fun fromJson(json: String): EditorProject = JsonReader(json).project()
    }
}

data class VideoClip(val id: String, val source: String, val sourceDurationMs: Long, val trimStartMs: Long = 0, val trimEndMs: Long = sourceDurationMs, val speed: Double = 1.0, val volume: Double = 1.0, val originalAudioEnabled: Boolean = true, val fadeInMs: Long = 0, val fadeOutMs: Long = 0, val minimumDurationMs: Long = 100) {
    init { require(id.isNotBlank() && source.isNotBlank()); require(sourceDurationMs > 0); require(trimStartMs >= 0 && trimEndMs > trimStartMs && trimEndMs <= sourceDurationMs); require(speed in listOf(.5, 1.0, 1.5, 2.0) && volume in 0.0..2.0); require(fadeInMs >= 0 && fadeOutMs >= 0 && fadeInMs + fadeOutMs <= trimEndMs - trimStartMs) }
}
data class MusicTrack(val id: String, val source: String, val startMs: Long = 0, val trimStartMs: Long = 0, val trimEndMs: Long, val volume: Double = 1.0, val fadeInMs: Long = 0, val fadeOutMs: Long = 0) {
    init { require(id.isNotBlank() && source.isNotBlank()); require(startMs >= 0 && trimStartMs >= 0 && trimEndMs > trimStartMs && volume in 0.0..2.0); require(fadeInMs >= 0 && fadeOutMs >= 0 && fadeInMs + fadeOutMs <= trimEndMs - trimStartMs) }
}
data class TextOverlay(val id: String, val text: String, val startMs: Long, val endMs: Long, val color: String = "#FFFFFF", val sizeSp: Int = 36, val x: Double = .5, val y: Double = .82) {
    init { require(id.isNotBlank() && text.isNotBlank() && startMs >= 0 && endMs > startMs); require(color in listOf("#FFFFFF", "#000000", "#FF5252", "#FFD740", "#69F0AE", "#40C4FF")); require(sizeSp in 12..120 && x in 0.0..1.0 && y in 0.0..1.0) }
    fun isVisibleAt(positionMs: Long): Boolean = positionMs >= startMs && positionMs < endMs
}
enum class EditorFilter { NONE, BLACK_WHITE, WARM, COOL, VIVID }
enum class AspectRatio { ORIGINAL, PORTRAIT_9_16, SQUARE_1_1, LANDSCAPE_16_9 }

private fun StringBuilder.quoted(value: String) { append('"'); value.forEach { c -> when (c) { '"' -> append("\\\""); '\\' -> append("\\\\"); '\n' -> append("\\n"); '\r' -> append("\\r"); '\t' -> append("\\t"); else -> if (c < ' ') append("\\u%04x".format(c.code)) else append(c) } }; append('"') }

/** Small strict reader for project JSON; avoids an Android or serialization runtime dependency. */
private class JsonReader(private val s: String) {
    private var p = 0
    fun project(): EditorProject {
        expect('{'); var filter = EditorFilter.NONE; var ratio = AspectRatio.ORIGINAL
        var clips = emptyList<VideoClip>(); var music = emptyList<MusicTrack>(); var texts = emptyList<TextOverlay>(); var ducking = false; var brightness = 0.0; var contrast = 0.0; var version = 0
        while (!take('}')) { val key = string(); expect(':'); when (key) {
            "version" -> version = number().toInt()
            "filter" -> filter = EditorFilter.valueOf(string())
            "aspectRatio" -> ratio = AspectRatio.valueOf(string())
            "brightness" -> brightness = number()
            "contrast" -> contrast = number()
            "clips" -> clips = array().map { VideoClip(it.str("id"), it.str("source"), it.long("sourceDurationMs"), it.long("trimStartMs"), it.long("trimEndMs"), it.num("speed"), it.num("volume"), it.bool("originalAudioEnabled"), it.long("fadeInMs"), it.long("fadeOutMs"), it.long("minimumDurationMs")) }
            "musicTracks" -> music = array().map { MusicTrack(it.str("id"), it.str("source"), it.long("startMs"), it.long("trimStartMs"), it.long("trimEndMs"), it.num("volume"), it.long("fadeInMs"), it.long("fadeOutMs")) }
            "textOverlays" -> texts = array().map { TextOverlay(it.str("id"), it.str("text"), it.long("startMs"), it.long("endMs"), it.str("color"), it.intOr("sizeSp", 36), it.doubleOr("x", .5), it.doubleOr("y", .82)) }
            "dialogueDucking" -> ducking = readScalar() as Boolean
            else -> skipValue()
        }; if (!take(',')) { expect('}'); break } }
        require(version == 1) { "Unsupported project version: $version" }
        require(p == s.length) { "Trailing JSON content" }
        return EditorProject(clips, music, texts, filter, ratio, ducking, brightness, contrast)
    }
    private fun array(): List<Map<String, Any>> { expect('['); val out = mutableListOf<Map<String, Any>>(); if (take(']')) return out; do { expect('{'); val fields = mutableMapOf<String, Any>(); while (true) { val k = string(); expect(':'); fields[k] = readScalar(); if (take('}')) break; expect(',') }; out += fields } while (take(',')); expect(']'); return out }
    private fun Map<String, Any>.str(k:String)=getValue(k) as String
    private fun Map<String, Any>.long(k:String)=(getValue(k) as Number).toLong()
    private fun Map<String, Any>.num(k:String)=(getValue(k) as Number).toDouble()
    private fun Map<String, Any>.bool(k:String)=(get(k) as? Boolean) ?: true
    private fun Map<String, Any>.doubleOr(k:String, default: Double)=(get(k) as? Number)?.toDouble() ?: default
    private fun Map<String, Any>.intOr(k:String, default: Int)=(get(k) as? Number)?.toInt() ?: default
    private fun readScalar(): Any { ws(); return when (s.getOrNull(p)) { '"' -> string(); 't' -> literal("true"); 'f' -> literal("false"); '-', in '0'..'9' -> number(); else -> error("Invalid JSON value at $p") } }
    private fun literal(value: String): Boolean { require(s.startsWith(value, p)); p += value.length; return value == "true" }
    private fun number(): Double { ws(); val start=p; while (s.getOrNull(p)?.let { it.isDigit() || it in ".-+eE" } == true) p++; return s.substring(start,p).toDouble() }
    private fun string(): String { ws(); expect('"'); val b=StringBuilder(); while (p<s.length) { val c=s[p++]; if(c=='"') return b.toString(); if(c!='\\') b.append(c) else { val e=s[p++]; b.append(when(e){'"'->'"';'\\'->'\\';'/'->'/';'b'->'\b';'f'->'\u000c';'n'->'\n';'r'->'\r';'t'->'\t';'u'->s.substring(p,p+4).toInt(16).toChar().also{p+=4};else->error("Invalid escape")}) } }; error("Unclosed string") }
    private fun skipValue() { readScalar() }
    private fun ws() { while (s.getOrNull(p)?.isWhitespace()==true) p++ }
    private fun take(c:Char):Boolean { ws(); if(s.getOrNull(p)==c){p++;return true};return false }
    private fun expect(c:Char) { require(take(c)) { "Expected '$c' at $p" } }
}
