package com.afudm.afutube

import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import com.afudm.afutube.core.theme.AfuColors
import info.bigwizardmedia.wizardcut.MainActivity as WizardCutActivity
import java.io.File

// Edit sekmesi yalnız kabuk: düzenleyici, proje listesi, dışa aktarma WizardCut'ın kendi ekranları.
@Composable
fun EditTabScreen() {
    val context = LocalContext.current
    Box(Modifier.fillMaxSize().background(AfuColors.bg), contentAlignment = Alignment.Center) {
        Column(Modifier.padding(28.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(Icons.Default.Movie, contentDescription = null, tint = AfuColors.accent, modifier = Modifier.size(52.dp))
            Spacer(Modifier.height(18.dp))
            Text("Video düzenle", color = AfuColors.text, style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.height(10.dp))
            Text("Kes, otomatik düzenle, altyazı ekle.", color = AfuColors.textMuted, textAlign = TextAlign.Center)
            Spacer(Modifier.height(24.dp))
            Button(
                onClick = { openWizardCut(context, WizardCutActivity.ACTION_NEW_PROJECT) },
                colors = ButtonDefaults.buttonColors(containerColor = AfuColors.accent),
                modifier = Modifier.fillMaxWidth().height(52.dp)
            ) { Text("Video seç") }
            TextButton(onClick = { openWizardCut(context, null) }) {
                Text("Son projeler", color = AfuColors.textMuted)
            }
        }
    }
}

private fun openWizardCut(context: Context, action: String?) {
    context.startActivity(Intent(context, WizardCutActivity::class.java).apply { if (action != null) setAction(action) })
}

/** İndirmeler > Editle: videoyu WizardCut'ın paylaşım girişine verir; WizardCut projeyi kurup editörü açar. */
fun openInWizardCut(context: Context, path: String) {
    val uri = runCatching {
        FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", File(path))
    }.getOrNull()
    if (uri == null) {
        Toast.makeText(context, "Video açılamadı. Dosya taşınmış olabilir.", Toast.LENGTH_LONG).show()
        return
    }
    val intent = Intent(context, WizardCutActivity::class.java).apply {
        action = Intent.ACTION_SEND
        type = context.contentResolver.getType(uri) ?: "video/*"
        putExtra(Intent.EXTRA_STREAM, uri)
        clipData = ClipData.newRawUri(null, uri)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    context.startActivity(intent)
}
