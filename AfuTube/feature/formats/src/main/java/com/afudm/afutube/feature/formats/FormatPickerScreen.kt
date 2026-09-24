package com.afudm.afutube.feature.formats

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import com.afudm.afutube.core.theme.AfuColors
import com.afudm.afutube.downloader.DownloadEngine

@Composable
fun FormatPickerScreen(
    mediaInfo: MediaInfo,
    onBack: () -> Unit = {},
    onDownload: (MediaFormat) -> Unit = {}
) {
    val context = LocalContext.current
    val simplified = remember(mediaInfo.formats) { FormatSimplifier.simplify(mediaInfo.formats) }
    var selectedOption by remember(mediaInfo) { mutableStateOf(simplified.defaultVideoOption) }

    Column(Modifier.fillMaxSize().background(AfuColors.bg)) {
        Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, null, tint = AfuColors.text) }
            Text("Format Seç", color = AfuColors.text, fontWeight = FontWeight.SemiBold, fontSize = 18.sp)
        }
        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            item { MediaInfoCard(mediaInfo) }
            if (simplified.videoOptions.isNotEmpty()) {
                item { SectionHeader("Video (MP4)") }
                items(simplified.videoOptions) { option ->
                    SimpleFormatRow(option, selectedOption == option) { selectedOption = option }
                }
            }
            if (simplified.hasAudio) {
                item { SectionHeader("Ses (MP3)") }
                items(simplified.audioOptions) { option ->
                    SimpleFormatRow(option, selectedOption == option) { selectedOption = option }
                }
            }
            item {
                Spacer(Modifier.height(8.dp))
                Button(
                    onClick = {
                        selectedOption?.let { option ->
                            val callbackFormat = option.sourceFormat ?: MediaFormat(
                                formatId = option.formatId,
                                ext = if (option.audioFormat == null) "mp4" else option.audioFormat,
                                quality = option.label,
                                resolution = "",
                                fps = 0,
                                vcodec = if (option.audioFormat == null) "unknown" else "none",
                                acodec = if (option.audioFormat == null) "none" else "unknown",
                                fileSizeB = 0,
                                url = ""
                            )
                            onDownload(callbackFormat)
                            startDownload(context, mediaInfo, option)
                        }
                    },
                    enabled = selectedOption != null,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = AfuColors.accent,
                        disabledContainerColor = AfuColors.surface
                    ),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Icon(Icons.Default.Download, null, modifier = Modifier.size(20.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = selectedOption?.let { "İndir — ${it.label}" } ?: "Format seç",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                Spacer(Modifier.height(32.dp))
            }
        }
    }
}

@Composable
private fun MediaInfoCard(info: MediaInfo) {
    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = AfuColors.card), shape = RoundedCornerShape(14.dp)) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            if (info.thumbnail.isNotBlank()) {
                AsyncImage(info.thumbnail, null, modifier = Modifier.size(70.dp, 52.dp).clip(RoundedCornerShape(8.dp)))
                Spacer(Modifier.width(12.dp))
            }
            Column(Modifier.weight(1f)) {
                Text(info.title, color = AfuColors.text, fontWeight = FontWeight.SemiBold, fontSize = 14.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
                if (info.uploader.isNotBlank()) Text(info.uploader, color = AfuColors.textMuted, fontSize = 12.sp)
                if (info.duration > 0) Text(formatDuration(info.duration), color = AfuColors.textMuted, fontSize = 12.sp)
            }
        }
    }
}

@Composable
private fun SectionHeader(title: String) {
    Text(title, color = AfuColors.text, fontWeight = FontWeight.SemiBold, fontSize = 15.sp, modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp))
}

@Composable
private fun SimpleFormatRow(option: FormatOption, isSelected: Boolean, onClick: () -> Unit) {
    val borderColor = if (isSelected) AfuColors.accent else Color.Transparent
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth().border(1.dp, borderColor, RoundedCornerShape(12.dp)),
        colors = CardDefaults.cardColors(containerColor = if (isSelected) AfuColors.accent.copy(alpha = 0.08f) else AfuColors.card),
        shape = RoundedCornerShape(12.dp)
    ) {
        Row(Modifier.padding(horizontal = 14.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(option.label, color = if (isSelected) AfuColors.accent else AfuColors.text, fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal, fontSize = 14.sp, modifier = Modifier.weight(1f))
            if (option.estimatedSize.isNotBlank()) Text(option.estimatedSize, color = AfuColors.textMuted, fontSize = 12.sp)
            Spacer(Modifier.width(8.dp))
            Icon(if (isSelected) Icons.Default.CheckCircle else Icons.Default.RadioButtonUnchecked, null,
                tint = if (isSelected) AfuColors.accent else AfuColors.textMuted, modifier = Modifier.size(20.dp))
        }
    }
}

private fun formatDuration(seconds: Int): String {
    val h = seconds / 3600
    val m = (seconds % 3600) / 60
    val s = seconds % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
}

private fun startDownload(context: Context, info: MediaInfo, option: FormatOption) {
    val format = option.sourceFormat
    val formatId = if (format != null) {
        if (!format.isAudioOnly && format.acodec == "none") "${format.formatId}+bestaudio/${format.formatId}" else format.formatId
    } else option.formatId
    DownloadEngine.getInstance(context).enqueue(
        DownloadEngine.DownloadRequest(
            url = info.sourceUrl,
            formatId = formatId,
            title = info.title,
            mergeAV = if (format != null) !format.isAudioOnly else option.mergeAV,
            audioFormat = option.audioFormat
        )
    )
}
