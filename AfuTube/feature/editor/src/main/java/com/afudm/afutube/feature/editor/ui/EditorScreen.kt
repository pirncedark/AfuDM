package com.afudm.afutube.feature.editor.ui

import android.content.Context
import android.content.Intent
import android.media.MediaMetadataRetriever
import android.media.MediaExtractor
import android.media.MediaCodec
import android.media.MediaFormat
import android.net.Uri
import android.os.Build
import android.Manifest
import android.util.LruCache
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.text.style.TextAlign
import androidx.media3.common.util.UnstableApi
import androidx.media3.common.util.ExperimentalApi
import androidx.media3.transformer.CompositionPlayer
import androidx.media3.ui.compose.PlayerSurface
import androidx.work.WorkInfo
import androidx.work.WorkManager
import com.afudm.afutube.core.share.ShareHelper
import com.afudm.afutube.core.theme.AfuColors
import com.afudm.afutube.feature.editor.engine.CompositionBuilder
import com.afudm.afutube.feature.editor.engine.ExportQuality
import com.afudm.afutube.feature.editor.engine.ExportWorker
import com.afudm.afutube.feature.downloads.audioArgs
import com.afudm.afutube.feature.downloads.audioOutput
import com.afudm.afutube.downloader.DownloadFolder
import com.afudm.afutube.runtime.FfmpegRunner
import com.afudm.afutube.feature.editor.history.ProjectEditCommand
import com.afudm.afutube.feature.editor.history.UndoStack
import com.afudm.afutube.feature.editor.model.EditorProject
import com.afudm.afutube.feature.editor.model.VideoClip
import com.afudm.afutube.feature.editor.model.TextOverlay
import com.afudm.afutube.feature.editor.model.EditorFilter
import com.afudm.afutube.feature.editor.model.AspectRatio
import com.afudm.afutube.feature.editor.model.TimelineMath
import com.afudm.afutube.media.loadMusic
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.util.UUID
import java.util.concurrent.TimeUnit

@OptIn(UnstableApi::class, ExperimentalApi::class)
@Composable
fun EditorScreen(
    initialProject: EditorProject,
    onAddClip: (onSelected: (VideoClip) -> Unit) -> Unit,
    onSave: (EditorProject) -> Unit,
    modifier: Modifier = Modifier,
    musicLibraryProvider: (suspend (Context) -> List<com.afudm.afutube.media.MusicTrack>)? = null
) {
    var project by remember { mutableStateOf(initialProject) }
    var revision by remember { mutableIntStateOf(0) }
    var player by remember { mutableStateOf<CompositionPlayer?>(null) }
    var draftReady by remember { mutableStateOf(false) }
    var showResume by remember { mutableStateOf(false) }
    var showFirstTip by remember { mutableStateOf(false) }
    var showExportOptions by remember { mutableStateOf(false) }
    var showAdvancedQuality by remember { mutableStateOf(false) }
    var selectedQuality by remember { mutableStateOf(ExportQuality.SOURCE) }
    var exportId by remember { mutableStateOf<UUID?>(null) }
    var audioMessage by remember { mutableStateOf<String?>(null) }
    var selectedClipId by remember(initialProject) { mutableStateOf<String?>(null) }
    var selectedTool by remember { mutableStateOf("Kes") }
    var selectedTextId by remember { mutableStateOf<String?>(null) }
    var musicLibrary by remember { mutableStateOf(emptyList<com.afudm.afutube.media.MusicTrack>()) }
    var showMusicLibrary by remember { mutableStateOf(false) }
    var positionMs by remember(player) { mutableLongStateOf(0L) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val musicPermission = if (Build.VERSION.SDK_INT >= 33) Manifest.permission.READ_MEDIA_AUDIO else Manifest.permission.READ_EXTERNAL_STORAGE
    val preferences = remember(context) { context.getSharedPreferences("editor_draft", Context.MODE_PRIVATE) }
    val exportInfo by exportId?.let { WorkManager.getInstance(context).getWorkInfoByIdFlow(it).collectAsState(initial = null) }
        ?: remember { mutableStateOf(null) }
    val history = remember { UndoStack() }
    val current by rememberUpdatedState(project)
    val activePlayer by rememberUpdatedState(player)
    fun edit(transform: (EditorProject) -> EditorProject) {
        history.execute(ProjectEditCommand({ current }, { project = it; revision++ }, transform))
    }
    fun addMusicSource(source: String) {
        val duration = project.clips.sumOf { (it.trimEndMs - it.trimStartMs).toDouble().div(it.speed).toLong() }.coerceAtLeast(1L)
        edit { it.copy(musicTracks = it.musicTracks + com.afudm.afutube.feature.editor.model.MusicTrack("music-${System.nanoTime()}", source, trimEndMs = duration)) }
    }
    val musicPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) scope.launch { musicLibrary = runCatching { musicLibraryProvider?.invoke(context) ?: loadMusic(context) }.getOrDefault(emptyList()); showMusicLibrary = true }
    }
    val audioDocumentLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri?.let { picked -> runCatching { context.contentResolver.takePersistableUriPermission(picked, Intent.FLAG_GRANT_READ_URI_PERMISSION) }; addMusicSource(picked.toString()) }
    }
    LaunchedEffect(initialProject) {
        val savedDraft = preferences.getString("project", null)
        showResume = !savedDraft.isNullOrBlank()
        draftReady = !showResume
        if (!showResume) showFirstTip = !preferences.getBoolean("intro_seen", false)
    }
    LaunchedEffect(project, draftReady) {
        if (draftReady) preferences.edit().putString("project", project.toJson()).apply()
    }
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
            TextButton(onClick = { onSave(project); showExportOptions = true }) { Text("Videoyu kaydet", color = AfuColors.text) }
        }
        var previewWidthPx by remember { mutableFloatStateOf(1f) }
        var previewHeightPx by remember { mutableFloatStateOf(1f) }
        val previewWidthDp = with(androidx.compose.ui.platform.LocalDensity.current) { previewWidthPx.toDp() }
        val previewHeightDp = with(androidx.compose.ui.platform.LocalDensity.current) { previewHeightPx.toDp() }
        Box(Modifier.fillMaxWidth().weight(1f).padding(vertical = 12.dp).clip(RoundedCornerShape(14.dp)).background(Color.Black).onSizeChanged { previewWidthPx=it.width.toFloat(); previewHeightPx=it.height.toFloat() }, Alignment.Center) {
            if (player != null) PlayerSurface(player = player!!, modifier = Modifier.fillMaxSize())
            else Text("Video ekle", color = AfuColors.textMuted)
            project.textOverlays.lastOrNull { it.isVisibleAt(positionMs) }?.let { overlay ->
                Text(overlay.text, color=Color(android.graphics.Color.parseColor(overlay.color)), fontSize=overlay.sizeSp.sp,
                    textAlign = TextAlign.Center,
                    modifier=Modifier.align(Alignment.TopStart).offset(x=previewWidthDp * overlay.x.toFloat(), y=previewHeightDp * overlay.y.toFloat())
                        .then(if (overlay.id == selectedTextId) Modifier.border(1.dp, AfuColors.accent) else Modifier)
                        .pointerInput(overlay.id) { detectTapGestures { selectedTextId = overlay.id; selectedTool = "Yazý" } }
                        .pointerInput(overlay.id, previewWidthPx, previewHeightPx) { detectDragGestures { change, drag -> change.consume(); selectedTextId = overlay.id; selectedTool = "Yazý"; edit { p -> p.updateText(overlay.id) { it.copy(x=(it.x+drag.x/previewWidthPx).coerceIn(0.0,1.0), y=(it.y+drag.y/previewHeightPx).coerceIn(0.0,1.0)) } } } })
            }
        }
        val durationMs = project.clips.sumOf { it.trimEndMs - it.trimStartMs }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { player?.let { if (it.isPlaying) it.pause() else it.play() } }) { Text(if (player?.isPlaying == true) "Duraklat" else "Oynat", color = AfuColors.text) }
        LaunchedEffect(player) { while (player != null) { positionMs = player?.currentPosition ?: 0L; kotlinx.coroutines.delay(250) } }
        Text("${formatTime(positionMs)} / ${formatTime(durationMs)}", Modifier.weight(1f), color = AfuColors.textMuted)
            TextButton(onClick = { if (history.undo()) revision++ }, enabled = history.canUndo) { Text("Geri al", color = AfuColors.accent) }
            TextButton(onClick = { if (history.redo()) revision++ }, enabled = history.canRedo) { Text("Ýleri al", color = AfuColors.accent) }
        }
        Timeline(
            clips = project.clips,
            selectedClipId = selectedClipId ?: TimelineMath.clipAtPlayhead(project.clips, positionMs)?.let { project.clips[it.index].id },
            onSelectClip = { selectedClipId = it },
            onTrim = { index, start, end -> edit { it.trimClip(index, start, end) } },
            onSplit = { edit { p -> TimelineMath.splitAtPlayhead(p, positionMs) } },
            onDelete = { index -> edit { it.removeClip(index) } },
            onReorder = { from, to -> edit { it.reorderClip(from, to) } },
            onAdd = { onAddClip { clip -> selectedClipId = clip.id; edit { it.copy(clips = it.clips + clip) } } },
            musicTracks = project.musicTracks,
            textOverlays = project.textOverlays,
            durationMs = durationMs,
            onEditText = { id, start, end -> edit { it.updateText(id) { text -> text.copy(startMs = start.coerceIn(0L, text.endMs - 1L), endMs = end.coerceIn(text.startMs + 1L, durationMs)) } } }
        )
        EditorTools(project = project, selectedClipId = selectedClipId ?: TimelineMath.clipAtPlayhead(project.clips, positionMs)?.let { project.clips[it.index].id }, playheadMs = positionMs, selectedTool = selectedTool, onSelectTool = { selectedTool = it }, selectedTextId = selectedTextId, onSelectText = { selectedTextId = it }, onEdit = { edit(it) }, onAddMusic = { source ->
            val duration = project.clips.maxOfOrNull { it.trimEndMs - it.trimStartMs } ?: 1_000L
            edit { it.copy(musicTracks = it.musicTracks + com.afudm.afutube.feature.editor.model.MusicTrack("music-${it.musicTracks.size}", source, trimEndMs = duration)) }
        }, onExtractAudio = {
            val source = project.clips.firstOrNull()?.source
            if (source == null) audioMessage = "Önce bir video ekle."
            else scope.launch {
                val input = File(Uri.parse(source).path ?: source)
                val output = audioOutput(input)
                val published = withContext(Dispatchers.IO) {
                    runCatching { if (FfmpegRunner.run(context, audioArgs(input, output)) == 0) DownloadFolder.publish(context, output) else null }
                }.getOrNull()
                audioMessage = if (published != null) "Ses ayrý dosya olarak kaydedildi." else "Ses kaydedilemedi. Tekrar dene."
            }
        }, onPickMusic = { if (musicLibraryProvider != null || androidx.core.content.ContextCompat.checkSelfPermission(context, musicPermission) == android.content.pm.PackageManager.PERMISSION_GRANTED) scope.launch { musicLibrary = runCatching { musicLibraryProvider?.invoke(context) ?: loadMusic(context) }.getOrDefault(emptyList()); showMusicLibrary = true } else musicPermissionLauncher.launch(musicPermission) }, onPickAudioFile = { audioDocumentLauncher.launch(arrayOf("audio/*")) })
    }

    if (showMusicLibrary) AlertDialog(onDismissRequest = { showMusicLibrary = false }, title = { Text("AfuTube Müzik") },
        text = { androidx.compose.foundation.lazy.LazyColumn { items(musicLibrary.size) { index -> val song = musicLibrary[index]; TextButton(onClick = { addMusicSource(song.uri); showMusicLibrary = false }) { Text("${song.title} · ${song.artist}", color = AfuColors.text) } } } },
        confirmButton = { TextButton(onClick = { showMusicLibrary = false }) { Text("Kapat") } })

    if (showResume) AlertDialog(
        onDismissRequest = { preferences.edit().remove("project").apply(); draftReady = true; showResume = false; showFirstTip = !preferences.getBoolean("intro_seen", false) },
        title = { Text("Kaldýðýn yerden devam?") },
        confirmButton = { TextButton(onClick = {
            val saved = preferences.getString("project", null)
            runCatching { saved?.let { EditorProject.fromJson(it) } }.getOrNull()?.let { project = it; revision++ }
            draftReady = true; showResume = false; showFirstTip = !preferences.getBoolean("intro_seen", false)
        }) { Text("Devam et") } },
        dismissButton = { TextButton(onClick = { preferences.edit().remove("project").apply(); draftReady = true; showResume = false; showFirstTip = !preferences.getBoolean("intro_seen", false) }) { Text("Yeni düzenleme") } }
    )
    if (showFirstTip) AlertDialog(
        onDismissRequest = { preferences.edit().putBoolean("intro_seen", true).apply(); showFirstTip = false },
        title = { Text("Üç adýmda düzenle") },
        text = { Text("1. Videonu seç.\n2. Alttaki araçlarla düzenle.\n3. Videoyu kaydet.") },
        confirmButton = { TextButton(onClick = { preferences.edit().putBoolean("intro_seen", true).apply(); showFirstTip = false }) { Text("Baþlayalým") } }
    )
    if (showExportOptions) AlertDialog(
        onDismissRequest = { showExportOptions = false },
        title = { Text("Videoyu kaydet") },
        text = {
            Column {
                Text("Kalite", color = AfuColors.text)
                listOf(ExportQuality.SOURCE to "Kaynak kalitesi").forEach { (quality, label) ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        RadioButton(selected = selectedQuality == quality, onClick = { selectedQuality = quality })
                        Text(label, color = AfuColors.text)
                    }
                }
                TextButton(onClick = { showAdvancedQuality = !showAdvancedQuality }) { Text(if (showAdvancedQuality) "Geliþmiþi gizle" else "Geliþmiþ", color = AfuColors.accent) }
                if (showAdvancedQuality) listOf(ExportQuality.P1080 to "1080p", ExportQuality.P720 to "720p").forEach { (quality, label) ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        RadioButton(selected = selectedQuality == quality, onClick = { selectedQuality = quality })
                        Text(label, color = AfuColors.text)
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = { exportId = ExportWorker.enqueue(context, project, selectedQuality); showExportOptions = false }) { Text("Kaydet") } },
        dismissButton = { TextButton(onClick = { showExportOptions = false }) { Text("Ýptal") } }
    )
    exportInfo?.let { info ->
        val output = info.outputData.getString(ExportWorker.KEY_OUTPUT)
        if (info.state == WorkInfo.State.RUNNING || info.state == WorkInfo.State.ENQUEUED) AlertDialog(
            onDismissRequest = {}, title = { Text("Video kaydediliyor") },
            text = { Column { LinearProgressIndicator(progress = { info.progress.getInt("progress_percent", 0) / 100f }, modifier = Modifier.fillMaxWidth()); Text("%${info.progress.getInt("progress_percent", 0)}") } }, confirmButton = { TextButton(onClick = { WorkManager.getInstance(context).cancelWorkById(info.id); exportId = null }) { Text("Durdur") } }
        ) else if (info.state == WorkInfo.State.FAILED) AlertDialog(
            onDismissRequest = { exportId = null }, title = { Text(ExportWorker.ERROR_MESSAGE) },
            confirmButton = { TextButton(onClick = {
                selectedQuality = if (selectedQuality == ExportQuality.P720) ExportQuality.P480 else ExportQuality.P720
                exportId = ExportWorker.enqueue(context, project, selectedQuality)
            }) { Text("Daha düþük kalitede tekrar dene") } },
            dismissButton = { TextButton(onClick = { exportId = null }) { Text("Kapat") } }
        ) else if (info.state == WorkInfo.State.SUCCEEDED && output != null) {
            val savedFile = File(output)
            AlertDialog(
                onDismissRequest = { exportId = null }, title = { Text("Video kaydedildi") }, text = { Text(savedFile.name) },
                confirmButton = { TextButton(onClick = { ShareHelper.shareFile(context, savedFile, savedFile.name) }) { Text("Paylaþ") } },
                dismissButton = { Row {
                    TextButton(onClick = {
                        val uri = ShareHelper.createShareUri(context, savedFile)
                        context.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(uri, "video/mp4").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION))
                    }) { Text("Aç") }
                    TextButton(onClick = {
                        val uri = ShareHelper.createShareUri(context, savedFile)
                        val intent = Intent(Intent.ACTION_SEND).setType("video/mp4").putExtra(Intent.EXTRA_STREAM, uri)
                            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                            .apply { clipData = android.content.ClipData.newUri(context.contentResolver, savedFile.name, uri) }
                        try { context.startActivity(intent.setPackage("com.whatsapp")) } catch (_: Exception) { ShareHelper.shareFile(context, savedFile, savedFile.name) }
                    }) { Text("WhatsApp") }
                } }
            )
        }
    }
    audioMessage?.let { message -> AlertDialog(onDismissRequest = { audioMessage = null }, text = { Text(message) }, confirmButton = { TextButton(onClick = { audioMessage = null }) { Text("Tamam") } }) }
    DisposableEffect(Unit) { onDispose { activePlayer?.release() } }
}

@Composable
private fun EditorTools(project: EditorProject, selectedClipId: String?, playheadMs: Long, selectedTool: String, onSelectTool: (String) -> Unit, selectedTextId: String?, onSelectText: (String?) -> Unit, onEdit: ((EditorProject) -> EditorProject) -> Unit, onAddMusic: (String) -> Unit, onExtractAudio: () -> Unit, onPickMusic: () -> Unit, onPickAudioFile: () -> Unit) {
    var musicPath by remember { mutableStateOf("") }
    var textDraft by remember { mutableStateOf("") }
    var textColor by remember { mutableStateOf("#FFFFFF") }
    val selectedClip = project.clips.firstOrNull { it.id == selectedClipId }
    val selectedText = project.textOverlays.firstOrNull { it.id == selectedTextId }
    Column(Modifier.fillMaxWidth().background(AfuColors.surface, RoundedCornerShape(12.dp)).padding(10.dp)) {
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            listOf("Kes", "Hýz", "Ses", "Müzik", "Yazý", "Filtre", "Oran", "Sesi ayýr").forEach { label -> TextButton(onClick = { onSelectTool(label); if (label == "Sesi ayýr") onExtractAudio() }) { Text(label, color = if (selectedTool == label) AfuColors.accent else AfuColors.text) } }
        }
        when (selectedTool) {
            "Kes" -> if (selectedClip != null) {
                val index = project.clips.indexOfFirst { it.id == selectedClip.id }
                Text("Baþlangýç · ${formatTime(selectedClip.trimStartMs)}", color = AfuColors.text)
                Slider(value = selectedClip.trimStartMs.toFloat(), onValueChange = { value -> onEdit { p -> p.trimClip(index, value.toLong(), p.clips[index].trimEndMs) } }, valueRange = 0f..(selectedClip.trimEndMs - selectedClip.minimumDurationMs).toFloat())
                Text("Bitiþ · ${formatTime(selectedClip.trimEndMs)}", color = AfuColors.text)
                Slider(value = selectedClip.trimEndMs.toFloat(), onValueChange = { value -> onEdit { p -> p.trimClip(index, p.clips[index].trimStartMs, value.toLong()) } }, valueRange = (selectedClip.trimStartMs + selectedClip.minimumDurationMs).toFloat()..selectedClip.sourceDurationMs.toFloat())
                Row {
                    TextButton(onClick = { onEdit { p -> TimelineMath.splitAtPlayhead(p, playheadMs) } }) { Text("Böl", color = AfuColors.text) }
                    TextButton(onClick = { onEdit { it.removeClip(index) } }) { Text("Sil", color = AfuColors.text) }
                }
            } else Text("Önce bir video ekle.", color = AfuColors.textMuted)
            "Hýz" -> Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                listOf(.5, 1.0, 1.5, 2.0).forEach { speed -> TextButton(onClick = { project.clips.indexOfFirst { it.id == selectedClipId }.takeIf { it >= 0 }?.let { index -> onEdit { p -> p.copy(clips = p.clips.toMutableList().also { it[index] = it[index].copy(speed = speed) }) } } }) { Text("${speed}x", color = AfuColors.text) } }
            }
            "Ses" -> {
                val index = project.clips.indexOfFirst { it.id == selectedClipId }
                val clip = project.clips.getOrNull(index)
                if (clip != null) {
                    Text("Klip sesi: ${(clip.volume * 100).toInt()}%", color = AfuColors.text)
                    Slider(value = clip.volume.toFloat(), onValueChange = { value -> onEdit { p -> p.copy(clips = p.clips.toMutableList().also { it[index] = it[index].copy(volume = value.toDouble()) }) } }, valueRange = 0f..2f)
                    Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(checked = !clip.originalAudioEnabled, onCheckedChange = { muted -> onEdit { p -> p.copy(clips = p.clips.toMutableList().also { it[index] = it[index].copy(originalAudioEnabled = !muted) }) } }); Text("Orijinal sesi kapat", color = AfuColors.text) }
                    Text("Yumuþak giriþ / çýkýþ", color = AfuColors.text)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf(0L, 300L, 600L, 1_000L).forEach { ms -> TextButton(onClick = { onEdit { p -> p.copy(clips = p.clips.toMutableList().also { it[index] = it[index].copy(fadeInMs = ms, fadeOutMs = ms.coerceAtMost((it[index].trimEndMs - it[index].trimStartMs) / 2)) }) } }) { Text("${ms / 1000.0}s", color = AfuColors.text) } }
                    }
                }
            }
            "Müzik" -> {
                Row {
                    TextButton(onClick = onPickMusic) { Text("AfuTube Müzik", color = AfuColors.text) }
                    TextButton(onClick = onPickAudioFile) { Text("Dosyadan seç", color = AfuColors.text) }
                    TextButton(onClick = { onEdit { it.copy(dialogueDucking = !it.dialogueDucking) } }) { Text("Konuþmada %30", color = AfuColors.text) }
                }
                project.musicTracks.forEachIndexed { i, track ->
                    Text("Müzik ${i + 1} · ${(track.volume * 100).toInt()}%", color = AfuColors.text)
                    Slider(value = track.volume.toFloat(), onValueChange = { value -> onEdit { p -> p.copy(musicTracks = p.musicTracks.toMutableList().also { it[i] = track.copy(volume = value.toDouble()) }) } }, valueRange = 0f..2f)
                    Text("Baþlangýç · ${formatTime(track.startMs)}", color = AfuColors.textMuted)
                    Slider(value = track.startMs.toFloat(), onValueChange = { value -> onEdit { p -> p.copy(musicTracks = p.musicTracks.toMutableList().also { it[i] = track.copy(startMs = value.toLong()) }) } }, valueRange = 0f..(project.clips.sumOf { it.trimEndMs - it.trimStartMs }).coerceAtLeast(1).toFloat())
                    Text("Kýrp · ${formatTime(track.trimStartMs)} – ${formatTime(track.trimEndMs)}", color = AfuColors.textMuted)
                    Row { TextButton(onClick = { onEdit { p -> p.copy(musicTracks = p.musicTracks.toMutableList().also { it[i] = track.copy(trimStartMs = (track.trimStartMs + 500).coerceAtMost(track.trimEndMs - 1)) }) } }) { Text("Baþýný kýrp +0,5 sn", color = AfuColors.text) }; TextButton(onClick = { onEdit { p -> p.copy(musicTracks = p.musicTracks.toMutableList().also { it[i] = track.copy(trimEndMs = (track.trimEndMs - 500).coerceAtLeast(track.trimStartMs + 1)) }) } }) { Text("Sonunu kýrp -0,5 sn", color = AfuColors.text) }; TextButton(onClick = { onEdit { p -> p.copy(musicTracks = p.musicTracks.filterIndexed { index, _ -> index != i }) } }) { Text("Kaldýr", color = AfuColors.text) } }
                    Row { TextButton(onClick = { onEdit { p -> p.copy(musicTracks = p.musicTracks.toMutableList().also { it[i] = track.copy(fadeInMs = 500L.coerceAtMost((track.trimEndMs - track.trimStartMs) / 2)) }) } }) { Text("Yumuþak giriþ", color = AfuColors.text) }; TextButton(onClick = { onEdit { p -> p.copy(musicTracks = p.musicTracks.toMutableList().also { it[i] = track.copy(fadeOutMs = 500L.coerceAtMost((track.trimEndMs - track.trimStartMs) / 2)) }) } }) { Text("Yumuþak çýkýþ", color = AfuColors.text) } }
                }
            }
            "Yazý" -> {
                OutlinedTextField(value = selectedText?.text ?: textDraft, onValueChange = { value -> if (selectedText != null) onEdit { p -> p.updateText(selectedText.id) { it.copy(text = value.ifBlank { " " }) } } else textDraft = value }, label = { Text("Yazý") }, singleLine = true)
                Row {
                    TextButton(onClick = { if (selectedText == null && textDraft.isNotBlank()) { val duration = project.clips.sumOf { (it.trimEndMs - it.trimStartMs).toDouble().div(it.speed).toLong() }.coerceAtLeast(1L); val overlay = TextOverlay("text-${System.nanoTime()}", textDraft, playheadMs.coerceAtMost(duration - 1), duration, textColor); onEdit { it.addText(overlay) }; onSelectText(overlay.id); textDraft = "" } }) { Text("Ekle", color = AfuColors.text) }
                    TextButton(onClick = { selectedText?.let { overlay -> onEdit { it.removeText(overlay.id) }; onSelectText(null) } }, enabled = selectedText != null) { Text("Sil", color = AfuColors.text) }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("#FFFFFF", "#000000", "#FF5252", "#FFD740", "#69F0AE", "#40C4FF").forEach { color ->
                        val chosen = selectedText?.color == color || (selectedText == null && textColor == color)
                        TextButton(onClick = { textColor = color; selectedText?.let { overlay -> onEdit { it.updateText(overlay.id) { value -> value.copy(color = color) } } } }, contentPadding = PaddingValues(horizontal = 6.dp)) { Box(Modifier.size(22.dp).background(Color(android.graphics.Color.parseColor(color)), RoundedCornerShape(11.dp)).then(if (chosen) Modifier.border(2.dp, AfuColors.accent, RoundedCornerShape(11.dp)) else Modifier)) }
                    }
                }
                if (selectedText != null) { val overlay = selectedText!!
                    Text("Boyut · ${overlay.sizeSp}", color = AfuColors.text)
                    Slider(value = overlay.sizeSp.toFloat(), onValueChange = { value -> onEdit { it.updateText(overlay.id) { text -> text.copy(sizeSp = value.toInt().coerceIn(12, 120)) } } }, valueRange = 12f..120f)
                    Text("Baþlangýç · ${formatTime(overlay.startMs)}", color = AfuColors.text)
                    Slider(value = overlay.startMs.toFloat(), onValueChange = { value -> onEdit { it.updateText(overlay.id) { text -> text.copy(startMs = value.toLong().coerceAtMost(text.endMs - 1)) } } }, valueRange = 0f..(overlay.endMs - 1).coerceAtLeast(0).toFloat())
                    Text("Bitiþ · ${formatTime(overlay.endMs)}", color = AfuColors.text)
                    val duration = project.clips.sumOf { (it.trimEndMs - it.trimStartMs).toDouble().div(it.speed).toLong() }.coerceAtLeast(1L)
                    Slider(value = overlay.endMs.toFloat(), onValueChange = { value -> onEdit { it.updateText(overlay.id) { text -> text.copy(endMs = value.toLong().coerceAtLeast(text.startMs + 1)) } } }, valueRange = (overlay.startMs + 1).toFloat()..duration.toFloat())
                } else Text("Önizlemede seçili yazýya dokunup düzenle.", color = AfuColors.textMuted)
                project.textOverlays.forEach { overlay -> TextButton(onClick = { onSelectText(overlay.id); textColor = overlay.color }) { Text(overlay.text, color = if (selectedTextId == overlay.id) AfuColors.accent else AfuColors.text) } }
            }
            "Filtre" -> {
                listOf(EditorFilter.NONE to "Yok", EditorFilter.BLACK_WHITE to "Siyah-Beyaz", EditorFilter.WARM to "Sýcak", EditorFilter.COOL to "Soðuk", EditorFilter.VIVID to "Canlý").forEach { (filter, label) -> TextButton(onClick = { onEdit { it.copy(filter = filter) } }) { Text(label, color = if (project.filter == filter) AfuColors.accent else AfuColors.text) } }
                Text("Parlaklýk · ${"%.1f".format(project.brightness)}", color = AfuColors.text)
                Slider(value = project.brightness.toFloat(), onValueChange = { value -> onEdit { it.copy(brightness = value.toDouble()) } }, valueRange = -1f..1f)
                Text("Kontrast · ${"%.1f".format(project.contrast)}", color = AfuColors.text)
                Slider(value = project.contrast.toFloat(), onValueChange = { value -> onEdit { it.copy(contrast = value.toDouble()) } }, valueRange = -1f..1f)
            }
            "Oran" -> listOf(AspectRatio.ORIGINAL to "Orijinal", AspectRatio.PORTRAIT_9_16 to "9:16", AspectRatio.SQUARE_1_1 to "1:1", AspectRatio.LANDSCAPE_16_9 to "16:9").forEach { (ratio, label) -> TextButton(onClick = { onEdit { it.copy(aspectRatio = ratio) } }) { Text(label, color = if (project.aspectRatio == ratio) AfuColors.accent else AfuColors.text) } }
            "Sesi ayýr" -> Text("Ses ayrý dosya olarak kaydedilir.", color = AfuColors.textMuted)
        }
    }
}

@Composable
private fun Timeline(clips: List<VideoClip>, selectedClipId: String?, onSelectClip: (String) -> Unit, onTrim: (Int, Long, Long) -> Unit, onSplit: (Int) -> Unit, onDelete: (Int) -> Unit, onReorder: (Int, Int) -> Unit, onAdd: () -> Unit, musicTracks: List<com.afudm.afutube.feature.editor.model.MusicTrack>, textOverlays: List<TextOverlay>, durationMs: Long, onEditText: (String, Long, Long) -> Unit) {
    var zoom by remember { mutableFloatStateOf(1f) }
    Column(Modifier.fillMaxWidth().background(AfuColors.surface, RoundedCornerShape(12.dp)).padding(10.dp)) {
        Box(Modifier.fillMaxWidth().pointerInput(Unit) { detectTransformGestures { _, _, zoomChange, _ -> zoom = (zoom * zoomChange).coerceIn(.5f, 4f) } }) {
        LazyRow(verticalAlignment = Alignment.CenterVertically) {
            itemsIndexed(clips, key = { _, clip -> clip.id }) { index, clip ->
                ClipStrip(clip, Modifier.semantics { contentDescription = "Klip ${index + 1}" }.width((clip.trimEndMs.minus(clip.trimStartMs).div(250).coerceIn(88L, 220L) * zoom).toInt().dp).height(76.dp).then(if (clip.id == selectedClipId) Modifier.border(2.dp, AfuColors.accent, RoundedCornerShape(8.dp)) else Modifier),
                    onTrim = { start, end -> onTrim(index, start, end) }, onTap = { onSelectClip(clip.id) }, onMove = { onReorder(index, (index + it).coerceIn(clips.indices)) })
            }
            item { TextButton(onClick = onAdd) { Text("+", color = AfuColors.accent, style = MaterialTheme.typography.headlineMedium) } }
        }
        if (musicTracks.isNotEmpty()) Row(Modifier.fillMaxWidth().height(24.dp), horizontalArrangement = Arrangement.spacedBy(3.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("d Müzik izi", color = AfuColors.accent)
            musicTracks.forEach { track ->
                val context = LocalContext.current
                val wave by produceState(emptyList<Float>(), track.source) { value = withContext(Dispatchers.IO) { WaveformCache.load(context, track.source) } }
                Box(Modifier.weight(1f).fillMaxHeight().padding(vertical = 3.dp).clip(RoundedCornerShape(4.dp)).background(AfuColors.card), contentAlignment = Alignment.CenterStart) {
                Canvas(Modifier.fillMaxSize()) { val count = wave.size; if (count > 0) repeat(count) { i -> val h = wave[i] * size.height; val x = size.width * i / count; drawLine(AfuColors.accent, Offset(x, (size.height - h) / 2), Offset(x, (size.height + h) / 2), 1.dp.toPx()) } }
            } }
        }
        if (textOverlays.isNotEmpty()) Row(Modifier.fillMaxWidth().height(24.dp), horizontalArrangement = Arrangement.spacedBy(3.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("T", color = AfuColors.accent)
            textOverlays.forEach { overlay ->
                val scale = 0.6f / durationMs.coerceAtLeast(1L).toFloat()
                Row(Modifier.weight(1f).height(24.dp).clip(RoundedCornerShape(4.dp)).background(AfuColors.card), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.width((overlay.startMs * scale).dp).fillMaxHeight())
                    Box(Modifier.width(12.dp).fillMaxHeight().background(AfuColors.accent).pointerInput(overlay, durationMs) { detectDragGestures { change, drag -> change.consume(); val delta = (drag.x / 0.6f * durationMs).toLong(); onEditText(overlay.id, (overlay.startMs + delta).coerceAtLeast(0L), overlay.endMs) } })
                    Text(overlay.text, color = AfuColors.text, maxLines = 1, modifier = Modifier.weight(1f).pointerInput(overlay, durationMs) { detectDragGestures { change, drag -> change.consume(); val delta = (drag.x / 0.6f * durationMs).toLong(); onEditText(overlay.id, overlay.startMs, (overlay.endMs + delta).coerceAtLeast(overlay.startMs + 1L)) } }.padding(horizontal = 2.dp))
                    Box(Modifier.width(12.dp).fillMaxHeight().background(AfuColors.accent).pointerInput(overlay, durationMs) { detectDragGestures { change, drag -> change.consume(); val delta = (drag.x / 0.6f * durationMs).toLong(); onEditText(overlay.id, overlay.startMs, (overlay.endMs + delta).coerceAtLeast(overlay.startMs + 1L)) } })
                }
            }
        }
        Canvas(Modifier.matchParentSize()) {
            drawLine(AfuColors.accent, Offset(size.width / 2, 0f), Offset(size.width / 2, size.height), 2.dp.toPx())
        }
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("${clips.size} klip", color = AfuColors.textMuted)
            Text("-", color = AfuColors.accent, modifier = Modifier.weight(1f))
            TextButton(onClick = { clips.indexOfFirst { it.id == selectedClipId }.takeIf { it >= 0 }?.let(onSplit) }, enabled = clips.isNotEmpty()) { Text("Böl", color = AfuColors.text) }
            TextButton(onClick = { clips.indexOfFirst { it.id == selectedClipId }.takeIf { it >= 0 }?.let(onDelete) }, enabled = clips.isNotEmpty()) { Text("Sil", color = AfuColors.text) }
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

private object WaveformCache {
    private val cache = object : LruCache<String, List<Float>>(24) {}

    fun load(context: Context, source: String): List<Float> {
        val uri = Uri.parse(source)
        val size = runCatching {
            context.contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.SIZE), null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) cursor.getLong(0) else -1L
            } ?: -1L
        }.getOrDefault(-1L)
        val key = "$source:$size"
        cache.get(key)?.let { return it }
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        try {
            extractor.setDataSource(context, uri, null)
            val track = (0 until extractor.trackCount).firstOrNull { extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true }
                ?: return List(200) { 0f }
            val format = extractor.getTrackFormat(track)
            extractor.selectTrack(track)
            codec = MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME)!!)
            codec.configure(format, null, null, 0)
            codec.start()
            val pcm = ArrayList<Short>()
            val info = MediaCodec.BufferInfo()
            var inputDone = false
            var outputDone = false
            while (!outputDone && pcm.size < 20_000_000) {
                if (!inputDone) {
                    val inputIndex = decoder.dequeueInputBuffer(10_000)
                    if (inputIndex >= 0) {
                        val input = decoder.getInputBuffer(inputIndex)!!
                        val count = extractor.readSampleData(input, 0)
                        if (count < 0) { decoder.queueInputBuffer(inputIndex, 0, 0, 0L, MediaCodec.BUFFER_FLAG_END_OF_STREAM); inputDone = true }
                        else { decoder.queueInputBuffer(inputIndex, 0, count, extractor.sampleTime, 0); extractor.advance() }
                    }
                }
                val outputIndex = decoder.dequeueOutputBuffer(info, 10_000)
                if (outputIndex >= 0) {
                    val output = decoder.getOutputBuffer(outputIndex)
                    if (output != null && info.size > 0) {
                        output.position(info.offset)
                        output.limit(info.offset + info.size)
                        while (output.remaining() >= 2) pcm.add(output.short)
                    }
                    outputDone = info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0
                    decoder.releaseOutputBuffer(outputIndex, false)
                }
            }
            val result = com.afudm.afutube.feature.editor.model.TimelineMath.rmsBuckets(ShortArray(pcm.size) { pcm[it] }, 200)
            cache.put(key, result)
            return result
        } catch (_: Exception) {
            return List(200) { 0f }
        } finally {
            runCatching { codec?.stop() }
            runCatching { codec?.release() }
            extractor.release()
        }
    }
}

private fun formatTime(ms: Long): String = String.format("%02d:%02d", TimeUnit.MILLISECONDS.toMinutes(ms), TimeUnit.MILLISECONDS.toSeconds(ms) % 60)
