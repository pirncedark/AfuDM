package com.afudm.afutube.feature.downloads

import android.media.MediaScannerConnection
import android.net.Uri
import android.widget.VideoView
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.unit.dp
import com.afudm.afutube.runtime.FfmpegRunner
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

@Composable
fun TrimDialog(path: String, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val file = remember(path) { File(path) }
    val scope = rememberCoroutineScope()
    var range by remember { mutableStateOf(0f..60f) }
    var working by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf(false) }
    AlertDialog(onDismissRequest = { if (!working) onDismiss() }, title = { Text("Videoyu kırp") }, text = {
        Column {
            AndroidView(factory = { VideoView(it).apply { setVideoURI(Uri.fromFile(file)); setOnPreparedListener { player -> range = 0f..(player.duration / 1000f).coerceAtLeast(1f); start() } } }, modifier = Modifier.fillMaxWidth().height(180.dp))
            RangeSlider(value = range, onValueChange = { range = it }, valueRange = 0f..(range.endInclusive.coerceAtLeast(1f)), steps = 0)
            Text("${range.start.toInt()} sn – ${range.endInclusive.toInt()} sn")
            if (error) Text("Video kırpılamadı. Tekrar dene.", color = MaterialTheme.colorScheme.error)
            if (working) LinearProgressIndicator(Modifier.fillMaxWidth())
        }
    }, confirmButton = { Button(enabled = !working, onClick = { working = true; error = false; scope.launch(Dispatchers.IO) {
        val output = trimOutput(file)
        val result = runCatching { FfmpegRunner.run(context, trimArgs(file, output, (range.start * 1000).toLong(), (range.endInclusive * 1000).toLong())) }
        if (result.getOrNull() == 0) MediaScannerConnection.scanFile(context, arrayOf(output.absolutePath), null, null)
        working = false; if (result.getOrNull() == 0) onDismiss() else error = true
    } }) { Text("Kırp ve kaydet") } }, dismissButton = { TextButton(onClick = onDismiss, enabled = !working) { Text("İptal") } })
}
