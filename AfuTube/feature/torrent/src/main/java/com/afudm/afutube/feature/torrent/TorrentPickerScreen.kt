package com.afudm.afutube.feature.torrent

import android.Manifest
import android.content.Context
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.afudm.afutube.core.theme.AfuColors
import com.afudm.afutube.downloader.DownloadEngine

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TorrentPickerScreen(onBack: () -> Unit = {}) {
    val context = LocalContext.current
    var magnetLink by remember { mutableStateOf("") }
    var fileUri    by remember { mutableStateOf("") }
    var status     by remember { mutableStateOf<String?>(null) }
    var isError    by remember { mutableStateOf(false) }

    // Dosya seçici (.torrent)
    val fileLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri ->
        uri?.let {
            fileUri = it.toString()
            magnetLink = "" // dosya seçilince magnet alanını temizle
            status = "Dosya seçildi: ${it.lastPathSegment}"
            isError = false
        }
    }

    // Depolama izni (Android < 10)
    val permLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (!granted) {
            status = "Depolama izni reddedildi."
            isError = true
        } else {
            fileLauncher.launch("*/*")
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AfuColors.bg)
    ) {
        // ── Toolbar ─────────────────────────────────────────────────────────
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.Default.ArrowBack, contentDescription = null, tint = AfuColors.text)
            }
            Text(
                text       = "Torrent İndir",
                color      = AfuColors.text,
                fontWeight = FontWeight.SemiBold,
                fontSize   = 18.sp
            )
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {

            // ── Bilgi kartı ─────────────────────────────────────────────────
            Card(
                colors = CardDefaults.cardColors(containerColor = AfuColors.card),
                shape  = RoundedCornerShape(14.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(14.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.Info, contentDescription = null, tint = AfuColors.accent)
                    Text(
                        text     = "Bir .torrent dosyası seçin veya magnet linkini yapıştırın. İndirme arka planda çalışır, bildirim ile takip edebilirsiniz.",
                        color    = AfuColors.textMuted,
                        fontSize = 12.sp,
                        lineHeight = 17.sp
                    )
                }
            }

            // ── .torrent dosya seçimi ────────────────────────────────────────
            SectionLabel("📁 .torrent Dosyası")

            OutlinedTextField(
                value         = fileUri,
                onValueChange = { fileUri = it },
                label         = { Text("Dosya yolu veya URI") },
                placeholder   = { Text("content://... ya da /storage/...", color = AfuColors.textMuted) },
                singleLine    = true,
                modifier      = Modifier.fillMaxWidth(),
                colors        = outlinedFieldColors(),
                trailingIcon  = {
                    if (fileUri.isNotBlank()) {
                        IconButton(onClick = { fileUri = "" }) {
                            Icon(Icons.Default.Clear, null, tint = AfuColors.textMuted)
                        }
                    }
                }
            )

            Button(
                onClick = {
                    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
                        permLauncher.launch(Manifest.permission.READ_EXTERNAL_STORAGE)
                    } else {
                        fileLauncher.launch("*/*")
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                shape    = RoundedCornerShape(10.dp),
                colors   = ButtonDefaults.buttonColors(containerColor = AfuColors.surface)
            ) {
                Icon(Icons.Default.FolderOpen, null, tint = AfuColors.accent)
                Spacer(Modifier.width(8.dp))
                Text("Dosya Seç", color = AfuColors.accent)
            }

            // ── VEYA ayırıcı ────────────────────────────────────────────────
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                HorizontalDivider(modifier = Modifier.weight(1f), color = AfuColors.surface)
                Text(
                    text     = "  VEYA  ",
                    color    = AfuColors.textMuted,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold
                )
                HorizontalDivider(modifier = Modifier.weight(1f), color = AfuColors.surface)
            }

            // ── Magnet link girişi ──────────────────────────────────────────
            SectionLabel("🧲 Magnet Link")

            OutlinedTextField(
                value         = magnetLink,
                onValueChange = {
                    magnetLink = it
                    fileUri = "" // magnet girilince dosya alanını temizle
                },
                label         = { Text("magnet:?xt=urn:btih:...") },
                singleLine    = false,
                maxLines      = 4,
                modifier      = Modifier.fillMaxWidth(),
                colors        = outlinedFieldColors(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                trailingIcon  = {
                    if (magnetLink.isNotBlank()) {
                        IconButton(onClick = { magnetLink = "" }) {
                            Icon(Icons.Default.Clear, null, tint = AfuColors.textMuted)
                        }
                    }
                }
            )

            // ── Durum mesajı ────────────────────────────────────────────────
            AnimatedVisibility(visible = status != null) {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = if (isError) Color(0xFF4C1717) else Color(0xFF1A3A1A)
                    ),
                    shape    = RoundedCornerShape(10.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Icon(
                            if (isError) Icons.Default.ErrorOutline else Icons.Default.CheckCircle,
                            contentDescription = null,
                            tint = if (isError) Color(0xFFFF6B6B) else Color(0xFF69DB7C)
                        )
                        Text(
                            text     = status ?: "",
                            color    = if (isError) Color(0xFFFF6B6B) else Color(0xFF69DB7C),
                            fontSize = 13.sp,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }
            }

            Spacer(Modifier.height(4.dp))

            // ── İndir butonu ────────────────────────────────────────────────
            val link = magnetLink.ifBlank { fileUri }
            Button(
                onClick = {
                    if (link.isBlank()) {
                        status = "Lütfen bir dosya seçin veya magnet link girin."
                        isError = true
                        return@Button
                    }
                    startTorrentDownload(context, link) { msg, err ->
                        status  = msg
                        isError = err
                    }
                },
                enabled  = link.isNotBlank(),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp),
                colors   = ButtonDefaults.buttonColors(
                    containerColor         = AfuColors.surface,
                    contentColor            = AfuColors.text,
                    disabledContainerColor = AfuColors.surface
                ),
                border = androidx.compose.foundation.BorderStroke(1.dp, AfuColors.accent),
                shape = RoundedCornerShape(12.dp)
            ) {
                Icon(Icons.Default.Download, null, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Text(
                    text       = "İndirmeyi Başlat",
                    fontSize   = 15.sp,
                    fontWeight = FontWeight.SemiBold
                )
            }

            Spacer(Modifier.height(32.dp))
        }
    }
}

// ── Yardımcılar ───────────────────────────────────────────────────────────────

@Composable
private fun SectionLabel(text: String) {
    Text(
        text       = text,
        color      = AfuColors.text,
        fontWeight = FontWeight.SemiBold,
        fontSize   = 14.sp
    )
}

@Composable
private fun outlinedFieldColors() = OutlinedTextFieldDefaults.colors(
    focusedBorderColor   = AfuColors.accent,
    unfocusedBorderColor = AfuColors.surface,
    focusedLabelColor    = AfuColors.accent,
    unfocusedLabelColor  = AfuColors.textMuted,
    focusedTextColor     = AfuColors.text,
    unfocusedTextColor   = AfuColors.text,
    cursorColor          = AfuColors.accent,
    focusedContainerColor   = AfuColors.card,
    unfocusedContainerColor = AfuColors.card
)

private fun startTorrentDownload(
    context   : Context,
    uri       : String,
    onResult  : (message: String, isError: Boolean) -> Unit
) {
    if (uri.startsWith("magnet:", ignoreCase = true)) {
        // Şu an magnet desteklenmiyor — kullanıcıya bildir
        onResult("Magnet linkler henüz desteklenmiyor. .torrent dosyası kullanın.", true)
        return
    }

    DownloadEngine.getInstance(context).enqueue(
        DownloadEngine.DownloadRequest(
            url   = uri,
            title = "Torrent_${System.currentTimeMillis()}",
            kind  = DownloadEngine.Kind.TORRENT
        )
    )
    onResult("İndirme sıraya alındı. Bildirimlerden takip edebilirsiniz.", false)
}
