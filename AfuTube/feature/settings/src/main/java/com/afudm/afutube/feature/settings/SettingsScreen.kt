package com.afudm.afutube.feature.settings

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.afudm.afutube.core.theme.AfuColors
import com.afudm.afutube.core.diagnostics.LastAnalysisErrorStore
import com.afudm.afutube.updater.ExtractorUpdater
import com.afudm.afutube.updater.AppUpdate
import com.afudm.afutube.updater.UpdateManager
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(
    currentVersionCode: Int = 1000000,
    onUpdateFound: (AppUpdate) -> Unit = {}
) {
    val context = LocalContext.current
    val scope   = rememberCoroutineScope()
    var ytdlpVersion by remember { mutableStateOf("…") }
    var updateStatus by remember { mutableStateOf("") }
    var isUpdating   by remember { mutableStateOf(false) }
    var channel      by remember { mutableStateOf(ExtractorUpdater.Channel.STABLE) }
    var autoUpdate   by remember { mutableStateOf(UpdateManager.autoCheckEnabled(context)) }
    var appUpdateStatus by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        ytdlpVersion = ExtractorUpdater.currentVersion(context)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AfuColors.bg)
    ) {
        Text(
            "Ayarlar",
            color      = AfuColors.text,
            fontSize   = 22.sp,
            fontWeight = FontWeight.Bold,
            modifier   = Modifier.padding(20.dp)
        )

        LazyColumn(
            contentPadding      = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            item {
                LastAnalysisErrorStore.get()?.let { error ->
                    SettingsCard(title = "Tanı / Son hata") {
                        Text(error.categoryLabel, color = AfuColors.warning, fontSize = 13.sp)
                        Text("yt-dlp ${error.ytDlpVersion} · exit ${error.exitCode ?: "yok"}", color = AfuColors.textMuted, fontSize = 12.sp)
                        Text(error.traceback, color = AfuColors.textMuted, fontSize = 11.sp, maxLines = 8, overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
                    }
                }
            }
            item {
                SettingsCard(title = "Uygulama guncellemeleri") {
                    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("Guncellemeleri denetle", color = AfuColors.text, fontSize = 14.sp)
                            Text("Acilista gunde bir sessizce kontrol et", color = AfuColors.textMuted, fontSize = 12.sp)
                        }
                        Switch(checked = autoUpdate, onCheckedChange = {
                            autoUpdate = it
                            UpdateManager.setAutoCheckEnabled(context, it)
                        })
                    }
                    Spacer(Modifier.height(8.dp))
                    Button(onClick = {
                        scope.launch {
                            appUpdateStatus = "Denetleniyor..."
                            runCatching { UpdateManager.check(currentVersionCode) }
                                .onSuccess { update ->
                                    if (update == null) appUpdateStatus = "Uygulama guncel"
                                    else { appUpdateStatus = "Yeni surum bulundu"; onUpdateFound(update) }
                                }
                                .onFailure { appUpdateStatus = "Denetleme basarisiz: ${it.localizedMessage ?: "ag hatasi"}" }
                        }
                    }, modifier = Modifier.fillMaxWidth()) { Text("Guncellemeleri denetle") }
                    if (appUpdateStatus.isNotBlank()) Text(appUpdateStatus, color = AfuColors.textMuted, fontSize = 12.sp)
                }
            }
            // ── Extractor güncelleyici ──────────────────────────────────────
            item {
                SettingsCard(title = "🔧 Extractor (yt-dlp)") {
                    // Versiyon
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text("Mevcut versiyon", color = AfuColors.textMuted, fontSize = 12.sp)
                            Text(ytdlpVersion, color = AfuColors.text, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                        }
                        if (updateStatus.isNotBlank()) {
                            Text(updateStatus, color = AfuColors.success, fontSize = 12.sp)
                        }
                    }

                    Spacer(Modifier.height(10.dp))

                    // Kanal seçimi
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(
                            selected = channel == ExtractorUpdater.Channel.STABLE,
                            onClick  = { channel = ExtractorUpdater.Channel.STABLE },
                            label    = { Text("Stable") },
                            colors   = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = AfuColors.accent,
                                selectedLabelColor     = androidx.compose.ui.graphics.Color.White
                            )
                        )
                        FilterChip(
                            selected = channel == ExtractorUpdater.Channel.NIGHTLY,
                            onClick  = { channel = ExtractorUpdater.Channel.NIGHTLY },
                            label    = { Text("Nightly") },
                            colors   = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = AfuColors.accentAlt,
                                selectedLabelColor     = androidx.compose.ui.graphics.Color.White
                            )
                        )
                    }

                    Spacer(Modifier.height(10.dp))

                    // Güncelle butonu
                    Button(
                        onClick = {
                            scope.launch {
                                isUpdating   = true
                                updateStatus = ""
                                val result = ExtractorUpdater.checkAndUpdate(context, channel)
                                ytdlpVersion = result.newVersion
                                updateStatus = if (result.updated) "✓ Güncellendi" else if (result.error.isNotBlank()) "Hata: ${result.error}" else "Zaten güncel"
                                isUpdating   = false
                            }
                        },
                        enabled  = !isUpdating,
                        modifier = Modifier.fillMaxWidth(),
                        colors   = ButtonDefaults.buttonColors(containerColor = AfuColors.surface),
                        shape    = RoundedCornerShape(10.dp)
                    ) {
                        if (isUpdating) {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp), color = AfuColors.accent, strokeWidth = 2.dp)
                            Spacer(Modifier.width(8.dp))
                            Text("Güncelleniyor…", color = AfuColors.text)
                        } else {
                            Icon(Icons.Default.Update, null, tint = AfuColors.accent, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(8.dp))
                            Text("yt-dlp'yi Güncelle", color = AfuColors.text)
                        }
                    }
                }
            }

            // ── Hakkında ────────────────────────────────────────────────────
            item {
                SettingsCard(title = "ℹ️ Hakkında") {
                    SettingsRow(Icons.Default.Info, "Uygulama", "AfuTube v1.0")
                    SettingsRow(Icons.Default.Code, "Motor", "youtubedl-android + yt-dlp")
                    SettingsRow(Icons.Default.Bolt, "İndirici", "aria2c (çoklu bağlantı)")
                    SettingsRow(Icons.Default.Movie, "İşleyici", "FFmpeg (merge/convert)")
                    SettingsRow(Icons.Default.Storage, "Depolama", "MediaStore / Downloads")
                }
            }

            // ── Yasal ────────────────────────────────────────────────────────
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors   = CardDefaults.cardColors(containerColor = AfuColors.warning.copy(alpha = 0.1f)),
                    shape    = RoundedCornerShape(12.dp)
                ) {
                    Row(modifier = Modifier.padding(14.dp), verticalAlignment = Alignment.Top) {
                        Icon(Icons.Default.Gavel, null, tint = AfuColors.warning, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(10.dp))
                        Text(
                            text     = "Bu uygulama yalnızca kullanıcının indirme yetkisine sahip olduğu içerikleri destekler. DRM korumalı içerik desteklenmez. YouTube içeriği için ilgili platform koşullarına uyunuz.",
                            color    = AfuColors.warning,
                            fontSize = 12.sp
                        )
                    }
                }
                Spacer(Modifier.height(20.dp))
            }
        }
    }
}

@Composable
private fun SettingsCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors   = CardDefaults.cardColors(containerColor = AfuColors.card),
        shape    = RoundedCornerShape(14.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, color = AfuColors.textMuted, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(12.dp))
            content()
        }
    }
}

@Composable
private fun SettingsRow(icon: ImageVector, label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(icon, null, tint = AfuColors.accent, modifier = Modifier.size(16.dp))
        Spacer(Modifier.width(10.dp))
        Text(label, color = AfuColors.textMuted, fontSize = 13.sp, modifier = Modifier.weight(1f))
        Text(value, color = AfuColors.text, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
    }
}
