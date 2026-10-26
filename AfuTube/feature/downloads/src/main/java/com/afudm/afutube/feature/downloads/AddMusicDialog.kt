package com.afudm.afutube.feature.downloads

import android.media.MediaScannerConnection
import android.content.pm.PackageManager
import android.os.Build
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import android.net.Uri
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.afudm.afutube.media.MusicTrack
import com.afudm.afutube.media.loadMusic
import com.afudm.afutube.runtime.FfmpegRunner
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

@Composable
fun AddMusicDialog(path: String, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var songs by remember { mutableStateOf(emptyList<MusicTrack>()) }
    var selected by remember { mutableStateOf<MusicTrack?>(null) }
    var lower by remember { mutableStateOf(true) }
    var working by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf(false) }
    val permission = if (Build.VERSION.SDK_INT >= 33) "android.permission.READ_MEDIA_AUDIO" else "android.permission.READ_EXTERNAL_STORAGE"
    var granted by remember { mutableStateOf(context.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED) }
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted = it }
    LaunchedEffect(granted) { if (granted) songs = runCatching { loadMusic(context) }.getOrDefault(emptyList()) }
    AlertDialog(onDismissRequest = { if (!working) onDismiss() }, title = { Text("Müzik ekle") }, text = {
        Column {
            if (!granted) TextButton(onClick = { permissionLauncher.launch(permission) }) { Text("Müziklere erişim ver") }
            LazyColumn(Modifier.heightIn(max = 240.dp)) { items(songs, key = { it.uri }) { song -> ListItem(headlineContent = { Text(song.title) }, supportingContent = { Text(song.artist) }, modifier = Modifier.clickable { selected = song }) } }
            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) { Checkbox(checked = lower, onCheckedChange = { lower = it }); Text("Videonun sesini kıs") }
            if (error) Text("Videoya müzik eklenemedi. Tekrar dene.", color = MaterialTheme.colorScheme.error)
            if (working) LinearProgressIndicator(Modifier.fillMaxWidth())
        }
    }, confirmButton = { Button(enabled = selected != null && !working, onClick = { val song = selected ?: return@Button; working = true; scope.launch(Dispatchers.IO) {
        val video = File(path); val output = musicOutput(video)
        val result = runCatching {
            val audio = File(context.cacheDir, "selected-music-${System.nanoTime()}.audio")
            context.contentResolver.openInputStream(Uri.parse(song.uri))!!.use { source -> audio.outputStream().use { destination -> source.copyTo(destination) } }
            val hasAudio = FfmpegRunner.hasAudio(context, video)
            FfmpegRunner.run(context, addMusicArgs(video, audio, output, lower, hasAudio)).also { audio.delete() }
        }
        if (result.getOrNull() == 0) MediaScannerConnection.scanFile(context, arrayOf(output.absolutePath), null, null)
        working = false; if (result.getOrNull() == 0) onDismiss() else error = true
    } }) { Text("Kaydet") } }, dismissButton = { TextButton(onClick = onDismiss, enabled = !working) { Text("İptal") } })
}
