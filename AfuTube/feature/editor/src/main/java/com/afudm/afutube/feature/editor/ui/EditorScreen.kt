package com.afudm.afutube.feature.editor.ui

import android.content.Context
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.util.LruCache
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.media3.common.util.UnstableApi
import androidx.media3.common.util.ExperimentalApi
import androidx.media3.transformer.CompositionPlayer
import androidx.media3.ui.compose.PlayerSurface
import com.afudm.afutube.core.theme.AfuColors
import com.afudm.afutube.feature.editor.engine.CompositionBuilder
import com.afudm.afutube.feature.editor.history.ProjectEditCommand
import com.afudm.afutube.feature.editor.history.UndoStack
import com.afudm.afutube.feature.editor.model.EditorProject
import com.afudm.afutube.feature.editor.model.VideoClip
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit

@OptIn(UnstableApi::class, ExperimentalApi::class)
@Composable
fun EditorScreen(
    initialProject: EditorProject,
    onAddClip: (onSelected: (VideoClip) -> Unit) -> Unit,
    onSave: (EditorProject) -> Unit,
    modifier: Modifier = Modifier
) {
    var project by remember { mutableStateOf(initialProject) }
    var revision by remember { mutableIntStateOf(0) }
    var player by remember { mutableStateOf<CompositionPlayer?>(null) }
    val history = remember { UndoStack() }
    val current by rememberUpdatedState(project)
    val activePlayer by rememberUpdatedState(player)
    fun edit(transform: (EditorProject) -> EditorProject) {
        history.execute(ProjectEditCommand({ current }, { project = it; revision++ }, transform))
    }
    val context = LocalContext.current
    LaunchedEffect(project, revision) {
        player?.release()
        player = project.clips.takeIf { it.isNotEmpty() }?.let {
            CompositionPlayer.Builder(context).build().also { compositionPlayer ->
                compositionPlayer.setComposition(CompositionBuilder.build(project).composition)
                compositionPlayer.prepare()
            }
        }
    }
    Column(modifier.fillMaxSize().background(AfuColors.bg).padding(16.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("Düzenle", color = AfuColors.text, style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
            TextButton(onClick = { onSave(project) }) { Text("Kaydet", color = AfuColors.text) }
        }
        Box(Modifier.fillMaxWidth().weight(1f).padding(vertical = 12.dp).clip(RoundedCornerShape(14.dp)).background(Color.Black), Alignment.Center) {
            if (player != null) PlayerSurface(player = player!!, modifier = Modifier.fillMaxSize())
            else Text("Video ekle", color = AfuColors.textMuted)
        }
        val durationMs = project.clips.sumOf { it.trimEndMs - it.trimStartMs }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { player?.let { if (it.isPlaying) it.pause() else it.play() } }) { Text(if (player?.isPlaying == true) "Duraklat" else "Oynat", color = AfuColors.text) }
            var positionMs by remember(player) { mutableLongStateOf(0L) }
        LaunchedEffect(player) { while (player != null) { positionMs = player?.currentPosition ?: 0L; kotlinx.coroutines.delay(250) } }
        Text("${formatTime(positionMs)} / ${formatTime(durationMs)}", Modifier.weight(1f), color = AfuColors.textMuted)
            TextButton(onClick = { if (history.undo()) revision++ }, enabled = history.canUndo) { Text("Geri al", color = AfuColors.accent) }
            TextButton(onClick = { if (history.redo()) revision++ }, enabled = history.canRedo) { Text("İleri al", color = AfuColors.accent) }
        }
        Timeline(
            clips = project.clips,
            onTrim = { index, start, end -> edit { it.trimClip(index, start, end) } },
            onSplit = { index -> edit { p -> p.splitClip(index, (p.clips[index].trimEndMs - p.clips[index].trimStartMs) / 2) } },
            onDelete = { index -> edit { it.removeClip(index) } },
            onReorder = { from, to -> edit { it.reorderClip(from, to) } },
            onAdd = { onAddClip { clip -> edit { it.copy(clips = it.clips + clip) } } }
        )
        EditorTools(project = project, onEdit = { edit(it) }, onAddMusic = { source ->
            val duration = project.clips.maxOfOrNull { it.trimEndMs - it.trimStartMs } ?: 1_000L
            edit { it.copy(musicTracks = it.musicTracks + com.afudm.afutube.feature.editor.model.MusicTrack("music-${it.musicTracks.size}", source, trimEndMs = duration)) }
        })
    }
    DisposableEffect(Unit) { onDispose { activePlayer?.release() } }
}

@Composable
private fun EditorTools(project: EditorProject, onEdit: ((EditorProject) -> EditorProject) -> Unit, onAddMusic: (String) -> Unit) {
    var selected by remember { mutableStateOf("Hız") }
    var musicPath by remember { mutableStateOf("") }
    Column(Modifier.fillMaxWidth().background(AfuColors.surface, RoundedCornerShape(12.dp)).padding(10.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
            listOf("Hız", "Ses", "Müzik").forEach { label -> TextButton(onClick = { selected = label }) { Text(label, color = if (selected == label) AfuColors.accent else AfuColors.text) } }
        }
        when (selected) {
            "Hız" -> Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                listOf(.5, 1.0, 1.5, 2.0).forEach { speed -> TextButton(onClick = { project.clips.lastIndex.takeIf { it >= 0 }?.let { index -> onEdit { p -> p.copy(clips = p.clips.toMutableList().also { it[index] = it[index].copy(speed = speed) }) } } }) { Text("${speed}x", color = AfuColors.text) } }
            }
            "Ses" -> {
                val index = project.clips.lastIndex
                val clip = project.clips.getOrNull(index)
                if (clip != null) {
                    Text("Klip sesi: ${(clip.volume * 100).toInt()}%", color = AfuColors.text)
                    Slider(value = clip.volume.toFloat(), onValueChange = { value -> onEdit { p -> p.copy(clips = p.clips.toMutableList().also { it[index] = it[index].copy(volume = value.toDouble()) }) } }, valueRange = 0f..2f)
                    Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(checked = !clip.originalAudioEnabled, onCheckedChange = { muted -> onEdit { p -> p.copy(clips = p.clips.toMutableList().also { it[index] = it[index].copy(originalAudioEnabled = !muted) }) } }); Text("Orijinal sesi kapat", color = AfuColors.text) }
                    Text("Yumuşak giriş / çıkış", color = AfuColors.text)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf(0L, 300L, 600L, 1_000L).forEach { ms -> TextButton(onClick = { onEdit { p -> p.copy(clips = p.clips.toMutableList().also { it[index] = it[index].copy(fadeInMs = ms, fadeOutMs = ms.coerceAtMost((it[index].trimEndMs - it[index].trimStartMs) / 2)) }) } }) { Text("${ms / 1000.0}s", color = AfuColors.text) } }
                    }
                }
            }
            else -> {
                OutlinedTextField(value = musicPath, onValueChange = { musicPath = it }, label = { Text("Müzik dosyası") }, singleLine = true)
                Row { TextButton(onClick = { if (musicPath.isNotBlank()) onAddMusic(musicPath) }) { Text("Ekle", color = AfuColors.text) }; TextButton(onClick = { onEdit { it.copy(dialogueDucking = !it.dialogueDucking) } }) { Text("Konuşmada %30", color = AfuColors.text) } }
                project.musicTracks.forEachIndexed { i, track -> Text("Müzik ${i + 1} · ${(track.volume * 100).toInt()}%", color = AfuColors.text) }
            }
        }
    }
}

@Composable
private fun Timeline(clips: List<VideoClip>, onTrim: (Int, Long, Long) -> Unit, onSplit: (Int) -> Unit, onDelete: (Int) -> Unit, onReorder: (Int, Int) -> Unit, onAdd: () -> Unit) {
    Column(Modifier.fillMaxWidth().background(AfuColors.surface, RoundedCornerShape(12.dp)).padding(10.dp)) {
        Box(Modifier.fillMaxWidth()) {
        LazyRow(verticalAlignment = Alignment.CenterVertically) {
            itemsIndexed(clips, key = { _, clip -> clip.id }) { index, clip ->
                ClipStrip(clip, Modifier.width(clip.trimEndMs.minus(clip.trimStartMs).div(250).coerceIn(88L, 220L).toInt().dp).height(76.dp),
                    onTrim = { start, end -> onTrim(index, start, end) }, onTap = { }, onMove = { onReorder(index, (index + it).coerceIn(clips.indices)) })
            }
            item { TextButton(onClick = onAdd) { Text("+", color = AfuColors.accent, style = MaterialTheme.typography.headlineMedium) } }
        }
        Canvas(Modifier.matchParentSize()) {
            drawLine(AfuColors.accent, Offset(size.width / 2, 0f), Offset(size.width / 2, size.height), 2.dp.toPx())
        }
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("│", color = AfuColors.accent, modifier = Modifier.weight(1f))
            TextButton(onClick = { clips.indices.lastOrNull()?.let(onSplit) }, enabled = clips.isNotEmpty()) { Text("Böl", color = AfuColors.text) }
            TextButton(onClick = { clips.indices.lastOrNull()?.let(onDelete) }, enabled = clips.isNotEmpty()) { Text("Sil", color = AfuColors.text) }
        }
    }
}

@Composable
private fun ClipStrip(clip: VideoClip, modifier: Modifier, onTrim: (Long, Long) -> Unit, onTap: () -> Unit, onMove: (Int) -> Unit) {
    val context = LocalContext.current
    val frames by produceState<List<android.graphics.Bitmap?>>(emptyList(), clip.source, clip.trimStartMs, clip.trimEndMs) {
        value = withContext(Dispatchers.IO) { ThumbnailCache.frames(context, clip.source, clip.trimStartMs, clip.trimEndMs) }
    }
    var widthPx by remember { mutableFloatStateOf(1f) }
    var dragDistance by remember(clip.id) { mutableFloatStateOf(0f) }
    Row(modifier.pointerInput(clip) {
        detectDragGesturesAfterLongPress(onDragStart = { dragDistance = 0f }, onDragEnd = { }, onDrag = { change, drag ->
            change.consume()
            val amount = (drag.x / widthPx * (clip.trimEndMs - clip.trimStartMs)).toLong()
            val start = (clip.trimStartMs + amount).coerceIn(0, clip.trimEndMs - clip.minimumDurationMs)
            if (change.position.x < 14.dp.toPx()) onTrim(start, clip.trimEndMs)
            else if (change.position.x > widthPx - 14.dp.toPx()) onTrim(clip.trimStartMs, (clip.trimEndMs + amount).coerceIn(clip.trimStartMs + clip.minimumDurationMs, clip.sourceDurationMs))
            else { dragDistance += drag.x; if (kotlin.math.abs(dragDistance) > widthPx * .6f) { onMove(if (dragDistance > 0) 1 else -1); dragDistance = 0f } }
        })
    }.pointerInput(clip) { detectTapGestures { onTap() } }.clip(RoundedCornerShape(8.dp)).background(AfuColors.card).onSizeChanged { widthPx = it.width.toFloat() }) {
        Box(Modifier.width(14.dp).fillMaxHeight().background(AfuColors.accent.copy(alpha = .18f)))
        frames.forEach { bitmap -> if (bitmap != null) androidx.compose.foundation.Image(bitmap.asImageBitmap(), null, Modifier.weight(1f).fillMaxHeight()) else Box(Modifier.weight(1f).fillMaxHeight().background(AfuColors.card)) }
        Box(Modifier.width(14.dp).fillMaxHeight().background(AfuColors.accent.copy(alpha = .18f)))
    }
}

private object ThumbnailCache {
    private val cache = object : LruCache<String, List<android.graphics.Bitmap?>>(48) {}
    fun frames(context: Context, source: String, startMs: Long, endMs: Long): List<android.graphics.Bitmap?> {
        val key = "$source:$startMs:$endMs"
        cache.get(key)?.let { return it }
        val retriever = MediaMetadataRetriever()
        return try {
            retriever.setDataSource(context, Uri.parse(source))
            List(6) { i -> retriever.getFrameAtTime((startMs + (endMs - startMs) * i / 6) * 1000, MediaMetadataRetriever.OPTION_CLOSEST_SYNC) }
                .also { cache.put(key, it) }
        } catch (_: Exception) { List(6) { null } } finally { retriever.release() }
    }
}

private fun formatTime(ms: Long): String = String.format("%02d:%02d", TimeUnit.MILLISECONDS.toMinutes(ms), TimeUnit.MILLISECONDS.toSeconds(ms) % 60)
