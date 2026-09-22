package com.afudm.afutube.feature.downloads

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.work.WorkInfo
import com.afudm.afutube.downloader.DownloadEngine
import com.afudm.afutube.downloader.DownloadProgress
import com.afudm.afutube.feature.home.AfuColors
import java.util.UUID

@Composable
fun DownloadsScreen() {
    val context   = LocalContext.current
    val engine    = remember { DownloadEngine.getInstance(context) }
    val workInfos by engine.allDownloads().collectAsState(initial = emptyList())

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AfuColors.bg)
    ) {
        // ── Başlık ────────────────────────────────────────────────────────
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                "İndirmeler",
                color      = AfuColors.text,
                fontSize   = 22.sp,
                fontWeight = FontWeight.Bold
            )
            if (workInfos.any { it.state == WorkInfo.State.RUNNING }) {
                OutlinedButton(
                    onClick = { engine.cancelAll() },
                    colors  = ButtonDefaults.outlinedButtonColors(contentColor = AfuColors.error),
                    border  = androidx.compose.foundation.BorderStroke(1.dp, AfuColors.error.copy(0.4f))
                ) {
                    Icon(Icons.Default.StopCircle, null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("Tümünü Durdur", fontSize = 13.sp)
                }
            }
        }

        if (workInfos.isEmpty()) {
            // ── Boş durum ──────────────────────────────────────────────────
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        Icons.Default.DownloadDone,
                        null,
                        tint     = AfuColors.textMuted,
                        modifier = Modifier.size(56.dp)
                    )
                    Spacer(Modifier.height(12.dp))
                    Text("Aktif indirme yok", color = AfuColors.textMuted, fontSize = 15.sp)
                    Text("Ana ekrandan URL ekle", color = AfuColors.textMuted, fontSize = 13.sp)
                }
            }
        } else {
            LazyColumn(
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                items(workInfos, key = { it.id }) { workInfo ->
                    DownloadCard(
                        workInfo = workInfo,
                        onCancel = { engine.cancel(workInfo.id) }
                    )
                }
            }
        }
    }
}

@Composable
private fun DownloadCard(
    workInfo : WorkInfo,
    onCancel : () -> Unit
) {
    val percent = workInfo.progress.getInt("progress_percent", 0)
    val speed   = workInfo.progress.getString("progress_speed") ?: ""
    val size    = workInfo.progress.getString("progress_size") ?: ""
    val eta     = workInfo.progress.getLong("progress_eta", 0)
    val title   = workInfo.tags
        .firstOrNull { it.startsWith("title:") }
        ?.removePrefix("title:") ?: "İndiriliyor…"

    val (stateColor, stateIcon, stateLabel) = when (workInfo.state) {
        WorkInfo.State.RUNNING   -> Triple(AfuColors.accent, Icons.Default.Downloading, "İndiriliyor")
        WorkInfo.State.SUCCEEDED -> Triple(AfuColors.success, Icons.Default.CheckCircle, "Tamamlandı")
        WorkInfo.State.FAILED    -> Triple(AfuColors.error, Icons.Default.ErrorOutline, "Hata")
        WorkInfo.State.CANCELLED -> Triple(AfuColors.textMuted, Icons.Default.Cancel, "İptal edildi")
        WorkInfo.State.ENQUEUED  -> Triple(AfuColors.warning, Icons.Default.Schedule, "Bekliyor")
        else                     -> Triple(AfuColors.textMuted, Icons.Default.HourglassEmpty, "…")
    }

    Card(
        modifier  = Modifier.fillMaxWidth(),
        colors    = CardDefaults.cardColors(containerColor = AfuColors.card),
        shape     = RoundedCornerShape(14.dp)
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            // Başlık + durum
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(stateIcon, null, tint = stateColor, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(8.dp))
                Text(
                    text       = title,
                    color      = AfuColors.text,
                    fontSize   = 13.sp,
                    fontWeight = FontWeight.SemiBold,
                    maxLines   = 1,
                    overflow   = TextOverflow.Ellipsis,
                    modifier   = Modifier.weight(1f)
                )
                if (workInfo.state == WorkInfo.State.RUNNING) {
                    IconButton(onClick = onCancel, modifier = Modifier.size(32.dp)) {
                        Icon(Icons.Default.Close, null, tint = AfuColors.textMuted, modifier = Modifier.size(18.dp))
                    }
                }
            }

            // İlerleme çubuğu
            if (workInfo.state == WorkInfo.State.RUNNING || workInfo.state == WorkInfo.State.ENQUEUED) {
                Spacer(Modifier.height(10.dp))
                LinearProgressIndicator(
                    progress   = { percent / 100f },
                    modifier   = Modifier.fillMaxWidth().clip(RoundedCornerShape(4.dp)).height(6.dp),
                    color      = AfuColors.accent,
                    trackColor = AfuColors.surface
                )
                Spacer(Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("$percent%", color = AfuColors.accent, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        if (size.isNotBlank()) Text(size, color = AfuColors.textMuted, fontSize = 11.sp)
                        if (speed.isNotBlank()) Text(speed, color = AfuColors.text, fontSize = 11.sp)
                        if (eta > 0) Text("ETA ${formatEta(eta)}", color = AfuColors.textMuted, fontSize = 11.sp)
                    }
                }
            }

            // Durum metni (tamamlandı/hata)
            if (workInfo.state != WorkInfo.State.RUNNING && workInfo.state != WorkInfo.State.ENQUEUED) {
                Spacer(Modifier.height(4.dp))
                Text(stateLabel, color = stateColor, fontSize = 12.sp)
                workInfo.outputData.getString("error")?.let { err ->
                    if (err.isNotBlank()) Text(err, color = AfuColors.error, fontSize = 11.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
            }
        }
    }
}

private fun formatEta(seconds: Long): String = when {
    seconds >= 3600 -> "${seconds / 3600}s ${(seconds % 3600) / 60}dk"
    seconds >= 60   -> "${seconds / 60}dk ${seconds % 60}sn"
    else            -> "${seconds}sn"
}
