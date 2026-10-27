package com.afudm.afutube.feature.downloads

import android.media.MediaScannerConnection
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import com.afudm.afutube.core.theme.AfuColors
import com.afudm.afutube.runtime.FfmpegRunner
import com.afudm.afutube.media.PlayerActivity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

@Composable
fun EditDialog(path: String, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val input = remember(path) { File(path) }
    val player = remember(path) { ExoPlayer.Builder(context).build().apply { setMediaItem(MediaItem.fromUri(Uri.fromFile(input))); prepare() } }
    DisposableEffect(player) { onDispose { player.release() } }
    var duration by remember { mutableLongStateOf(0L) }
    var start by remember { mutableLongStateOf(0L) }
    var end by remember { mutableLongStateOf(0L) }
    var position by remember { mutableLongStateOf(0L) }
    var music by remember { mutableStateOf<File?>(null) }
    var originalVolume by remember { mutableFloatStateOf(1f) }
    var musicVolume by remember { mutableFloatStateOf(1f) }
    var muteOriginal by remember { mutableStateOf(false) }
    var tab by remember { mutableStateOf("Kırp") }
    var working by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var saved by remember { mutableStateOf<File?>(null) }
    val pickMusic = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) scope.launch(Dispatchers.IO) {
            runCatching { val copy = File(context.cacheDir, "edit-music-${System.nanoTime()}.audio"); context.contentResolver.openInputStream(uri)!!.use { src -> copy.outputStream().use(src::copyTo) }; copy }
                .onSuccess { music = it }.onFailure { error = "Müzik a??lamad?. Ba?ka bir dosya se?." }
        }
    }
    LaunchedEffect(player) {
        while (true) { duration = player.duration.coerceAtLeast(0L); position = player.currentPosition.coerceAtLeast(0L); if (end == 0L && duration > 0) end = duration; kotlinx.coroutines.delay(250) }
    }
    fun save(audioOnly: Boolean = false) {
        if (working) return
        working = true; error = null
        scope.launch {
            val output = if (audioOnly) audioOutput(input) else File(input.parentFile, "${input.nameWithoutExtension}_edit.mp4")
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    if (audioOnly) FfmpegRunner.run(context, audioArgs(input, output)) else {
                        val hasAudio = FfmpegRunner.hasAudio(context, input)
                        FfmpegRunner.run(context, editArgs(input, output, start, end.takeIf { it > 0 } ?: Long.MAX_VALUE, music, if (muteOriginal) 0 else (originalVolume * 100).toInt(), (musicVolume * 100).toInt(), hasAudio))
                    }
                }
            }
            working = false
            if (result.getOrNull() == 0) { MediaScannerConnection.scanFile(context, arrayOf(output.absolutePath), null, null); saved = output }
            else error = "Video kaydedilemedi. Tekrar dene."
        }
    }
    Dialog(onDismissRequest = { if (!working) onDismiss() }, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Column(Modifier.fillMaxSize().background(AfuColors.bg).padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { if (!working) onDismiss() }) { Icon(Icons.Default.Close, "Kapat", tint = AfuColors.text) }
                Text("Videoyu düzenle", color = AfuColors.text, modifier = Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
                TextButton(onClick = { save() }, enabled = !working && saved == null) { Text("Kaydet", color = AfuColors.accent) }
            }
            AndroidView(factory = { PlayerView(it).apply { this.player = player; useController = false; setBackgroundColor(android.graphics.Color.BLACK) } }, modifier = Modifier.fillMaxWidth().weight(0.8f).padding(vertical = 12.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { if (player.isPlaying) player.pause() else player.play() }) { Icon(if (player.isPlaying) Icons.Default.Pause else Icons.Default.PlayArrow, "Oynat veya duraklat", tint = AfuColors.accent) }
                Text("${editorClock(position)} / ${editorClock(duration)}", color = AfuColors.text)
            }
            Text("${editorClock(start)}     ${editorClock(end)}", color = AfuColors.textMuted, modifier = Modifier.align(Alignment.CenterHorizontally))
            Slider(value = position.coerceIn(0, duration.coerceAtLeast(1)).toFloat(), onValueChange = { position = it.toLong(); player.seekTo(position) }, valueRange = 0f..duration.coerceAtLeast(1).toFloat())
            RangeSlider(value = (start.toFloat()..end.coerceAtLeast(1).toFloat()), valueRange = 0f..duration.coerceAtLeast(1).toFloat(), onValueChange = { start = it.start.toLong(); end = it.endInclusive.toLong() })
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                listOf("Kırp", "Müzik", "Ses").forEachIndexed { i, name -> SegmentedButton(selected = tab == name, onClick = { tab = name }, shape = SegmentedButtonDefaults.itemShape(i, 3)) { Text(name) } }
            }
            when (tab) {
                "Müzik" -> Column(Modifier.weight(0.7f).fillMaxWidth(), verticalArrangement = Arrangement.Center) {
                    OutlinedButton(onClick = { pickMusic.launch(arrayOf("audio/*")) }, modifier = Modifier.fillMaxWidth()) { Text(if (music == null) "Müzik ekle" else music!!.name) }
                    music?.let { TextButton(onClick = { it.delete(); music = null }) { Text("Kaldır", color = AfuColors.accent) } }
                    Text("Müzik düzeyi: ${(musicVolume * 100).toInt()}%", color = AfuColors.text); Slider(musicVolume, { musicVolume = it }, valueRange = 0f..1f)
                }
                "Ses" -> Column(Modifier.weight(0.7f).fillMaxWidth(), verticalArrangement = Arrangement.Center) {
                    Row(verticalAlignment = Alignment.CenterVertically) { Text("Orijinal sesi kapat", color = AfuColors.text, modifier = Modifier.weight(1f)); Switch(muteOriginal, { muteOriginal = it }) }
                    Text("Orijinal ses: ${(originalVolume * 100).toInt()}%", color = AfuColors.text); Slider(originalVolume, { originalVolume = it }, enabled = !muteOriginal, valueRange = 0f..1f)
                }
                else -> Spacer(Modifier.weight(0.7f))
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                TextButton(onClick = { save(audioOnly = true) }, enabled = !working && saved == null) { Text("Yalnız sesi kaydet", color = AfuColors.accent) }
            }
            if (working) LinearProgressIndicator(Modifier.fillMaxWidth(), color = AfuColors.accent)
            error?.let { Text(it, color = AfuColors.error) }
            saved?.let { output ->
                Text("Kaydedildi: ${output.name}", color = AfuColors.success)
                Row { TextButton(onClick = { com.afudm.afutube.core.share.ShareHelper.shareFile(context, output, output.name) }) { Text("Paylaş", color = AfuColors.accent) }; TextButton(onClick = { context.startActivity(PlayerActivity.intent(context, output.absolutePath, output.nameWithoutExtension).apply { if (output.extension == "m4a") putExtra(PlayerActivity.EXTRA_LISTEN, true) }) }) { Text("Aç", color = AfuColors.accent) } }
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}
private fun editorClock(ms: Long) = "%d:%02d".format(ms.coerceAtLeast(0) / 60000, (ms.coerceAtLeast(0) / 1000) % 60)
