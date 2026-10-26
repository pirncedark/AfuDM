package com.afudm.afutube.feature.downloads

import android.media.MediaScannerConnection
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCut
import androidx.compose.material.icons.filled.Headphones
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.VolumeOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import com.afudm.afutube.runtime.FfmpegRunner
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

@Composable
fun EditDialog(path: String, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val file = remember(path) { File(path) }
    var child by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf(false) }
    var savedName by remember { mutableStateOf<String?>(null) }
    val runEdit: (File, List<String>) -> Unit = { output, args ->
        working = true
        error = false
        scope.launch {
            val result = withContext(Dispatchers.IO) { runCatching { FfmpegRunner.run(context, args) } }
            working = false
            if (result.getOrNull() == 0) {
                MediaScannerConnection.scanFile(context, arrayOf(output.absolutePath), null, null)
                savedName = output.name
            } else {
                error = true
            }
        }
    }

    if (child == "trim") {
        TrimDialog(path) { child = null }
    } else if (child == "music") {
        AddMusicDialog(path) { child = null }
    } else {
        AlertDialog(
            onDismissRequest = { if (!working) onDismiss() },
            title = { Text("Videoyu düzenle") },
            text = {
                Column {
                    if (savedName == null) {
                        ListItem(headlineContent = { Text("Kırp") }, supportingContent = { Text("Videonun başını veya sonunu kes") },
                            leadingContent = { Icon(Icons.Default.ContentCut, null) },
                            modifier = Modifier.clickable(enabled = !working) { child = "trim" })
                        ListItem(headlineContent = { Text("Müzik ekle") }, supportingContent = { Text("Videoya bir müzik parçası ekle") },
                            leadingContent = { Icon(Icons.Default.MusicNote, null) },
                            modifier = Modifier.clickable(enabled = !working) { child = "music" })
                        ListItem(headlineContent = { Text("Sesi kapat") }, supportingContent = { Text("Videonun sesini kaldırıp kaydet") },
                            leadingContent = { Icon(Icons.Default.VolumeOff, null) },
                            modifier = Modifier.clickable(enabled = !working) { runEdit(muteOutput(file), muteArgs(file, muteOutput(file))) })
                        ListItem(headlineContent = { Text("Yalnız sesi kaydet") }, supportingContent = { Text("Videodaki sesi ayrı bir dosyaya çıkar") },
                            leadingContent = { Icon(Icons.Default.Headphones, null) },
                            modifier = Modifier.clickable(enabled = !working) { runEdit(audioOutput(file), audioArgs(file, audioOutput(file))) })
                    } else {
                        Text("Kaydedildi: $savedName")
                    }
                    if (working) LinearProgressIndicator(Modifier.fillMaxWidth())
                    if (error) Text("Video düzenlenemedi. Tekrar dene.", color = MaterialTheme.colorScheme.error)
                }
            },
            confirmButton = { TextButton(onClick = onDismiss, enabled = !working) { Text("Kapat") } }
        )
    }
}
