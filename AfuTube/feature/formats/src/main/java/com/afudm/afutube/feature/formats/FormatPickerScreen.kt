package com.afudm.afutube.feature.formats

import android.content.Context
import androidx.compose.animation.*
import androidx.compose.foundation.*
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
import coil.compose.AsyncImage
import com.afudm.afutube.core.extractor.MediaFormat
import com.afudm.afutube.core.extractor.MediaInfo
import com.afudm.afutube.downloader.DownloadEngine
import com.afudm.afutube.feature.home.AfuColors

@Composable
fun FormatPickerScreen(
    mediaInfo  : MediaInfo,
    onBack     : () -> Unit = {},
    onDownload : (MediaFormat) -> Unit = {}
) {
    val context = LocalContext.current
    var selectedFormat by remember { mutableStateOf<MediaFormat?>(null) }

    val videoFormats = remember(mediaInfo) {
        mediaInfo.formats.filter { !it.isAudioOnly }
    }
    val audioFormats = remember(mediaInfo) {
        mediaInfo.formats.filter { it.isAudioOnly }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AfuColors.bg)
    ) {
        // ── Toolbar ──────────────────────────────────────────────────────────
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.Default.ArrowBack, null, tint = AfuColors.text)
            }
            Text(
                text  = "Format Seç",
                color = AfuColors.text,
                fontWeight = FontWeight.SemiBold,
                fontSize = 18.sp
            )
        }

        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // ── Medya bilgisi ──────────────────────────────────────────────
            item {
                MediaInfoCard(mediaInfo)
            }

            // ── Video formatları ────────────────────────────────────────────
            if (videoFormats.isNotEmpty()) {
                item {
                    SectionHeader("🎬 Video", videoFormats.size)
                }
                items(videoFormats) { fmt ->
                    FormatRow(
                        format     = fmt,
                        isSelected = selectedFormat == fmt,
                        onClick    = { selectedFormat = if (selectedFormat == fmt) null else fmt }
                    )
                }
            }

            // ── Ses formatları ─────────────────────────────────────────────
            if (audioFormats.isNotEmpty()) {
                item {
                    SectionHeader("🎵 Ses / Audio", audioFormats.size)
                }
                items(audioFormats) { fmt ->
                    FormatRow(
                        format     = fmt,
                        isSelected = selectedFormat == fmt,
                        onClick    = { selectedFormat = if (selectedFormat == fmt) null else fmt }
                    )
                }
            }

            // ── İndir butonu ────────────────────────────────────────────────
            item {
                Spacer(Modifier.height(8.dp))
                Button(
                    onClick  = { selectedFormat?.let { onDownload(it); startDownload(context, mediaInfo, it) } },
                    enabled  = selectedFormat != null,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    colors   = ButtonDefaults.buttonColors(
                        containerColor         = AfuColors.accent,
                        disabledContainerColor = AfuColors.surface
                    ),
                    shape    = RoundedCornerShape(12.dp)
                ) {
                    Icon(Icons.Default.Download, null, modifier = Modifier.size(20.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text       = if (selectedFormat != null) "İndir — ${selectedFormat!!.label}" else "Format seç",
                        fontSize   = 15.sp,
                        fontWeight = FontWeight.SemiBold,
                        maxLines   = 1,
                        overflow   = TextOverflow.Ellipsis
                    )
                }
                Spacer(Modifier.height(32.dp))
            }
        }
    }
}

@Composable
private fun MediaInfoCard(info: MediaInfo) {
    Card(
        modifier  = Modifier.fillMaxWidth(),
        colors    = CardDefaults.cardColors(containerColor = AfuColors.card),
        shape     = RoundedCornerShape(14.dp)
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (info.thumbnail.isNotBlank()) {
                AsyncImage(
                    model   = info.thumbnail,
                    contentDescription = null,
                    modifier = Modifier
                        .size(70.dp, 52.dp)
                        .clip(RoundedCornerShape(8.dp))
                )
                Spacer(Modifier.width(12.dp))
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text       = info.title,
                    color      = AfuColors.text,
                    fontWeight = FontWeight.SemiBold,
                    fontSize   = 14.sp,
                    maxLines   = 2,
                    overflow   = TextOverflow.Ellipsis
                )
                if (info.uploader.isNotBlank()) {
                    Spacer(Modifier.height(3.dp))
                    Text(info.uploader, color = AfuColors.textMuted, fontSize = 12.sp)
                }
                if (info.duration > 0) {
                    Text(formatDuration(info.duration), color = AfuColors.textMuted, fontSize = 12.sp)
                }
            }
        }
    }
}

@Composable
private fun SectionHeader(title: String, count: Int) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(title, color = AfuColors.text, fontWeight = FontWeight.SemiBold, fontSize = 15.sp)
        Spacer(Modifier.width(8.dp))
        Text(
            "$count format",
            color    = AfuColors.textMuted,
            fontSize = 12.sp,
            modifier = Modifier
                .clip(RoundedCornerShape(6.dp))
                .background(AfuColors.surface)
                .padding(horizontal = 6.dp, vertical = 2.dp)
        )
    }
}

@Composable
private fun FormatRow(
    format     : MediaFormat,
    isSelected : Boolean,
    onClick    : () -> Unit
) {
    val borderColor = if (isSelected) AfuColors.accent else Color.Transparent
    val bgColor     = if (isSelected) AfuColors.accent.copy(alpha = 0.08f) else AfuColors.card

    Card(
        onClick  = onClick,
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, borderColor, RoundedCornerShape(12.dp)),
        colors   = CardDefaults.cardColors(containerColor = bgColor),
        shape    = RoundedCornerShape(12.dp)
    ) {
        Row(
            modifier = Modifier
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Format bilgisi
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text       = format.label,
                    color      = if (isSelected) AfuColors.accent else AfuColors.text,
                    fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
                    fontSize   = 14.sp
                )
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    FormatChip(format.ext.uppercase())
                    if (!format.isAudioOnly && format.vcodec.isNotBlank() && format.vcodec != "unknown")
                        FormatChip(format.vcodec.substringBefore('.'))
                    if (format.acodec.isNotBlank() && format.acodec != "none" && format.acodec != "unknown")
                        FormatChip(format.acodec.substringBefore('.'))
                }
            }
            Spacer(Modifier.width(8.dp))
            // Seçim göstergesi
            if (isSelected) {
                Icon(
                    Icons.Default.CheckCircle,
                    null,
                    tint = AfuColors.accent,
                    modifier = Modifier.size(22.dp)
                )
            } else {
                Icon(
                    Icons.Default.RadioButtonUnchecked,
                    null,
                    tint = AfuColors.textMuted,
                    modifier = Modifier.size(22.dp)
                )
            }
        }
    }
}

@Composable
private fun FormatChip(label: String) {
    Text(
        text     = label,
        color    = AfuColors.textMuted,
        fontSize = 10.sp,
        modifier = Modifier
            .clip(RoundedCornerShape(4.dp))
            .background(AfuColors.surface)
            .padding(horizontal = 5.dp, vertical = 2.dp)
    )
}

// ── Yardımcılar ───────────────────────────────────────────────────────────────

private fun formatDuration(seconds: Int): String {
    val h = seconds / 3600
    val m = (seconds % 3600) / 60
    val s = seconds % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
}

private fun startDownload(context: Context, info: MediaInfo, format: MediaFormat) {
    DownloadEngine.getInstance(context).enqueue(
        DownloadEngine.DownloadRequest(
            url      = info.sourceUrl,
            formatId = format.formatId,
            title    = info.title,
            mergeAV  = !format.isAudioOnly
        )
    )
}
