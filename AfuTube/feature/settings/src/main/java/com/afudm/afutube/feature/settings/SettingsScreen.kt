package com.afudm.afutube.feature.settings

import android.content.Context
import android.content.Intent
import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Update
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.FileProvider
import com.afudm.afutube.core.diagnostics.LastAnalysisErrorStore
import com.afudm.afutube.core.theme.AfuColors
import com.afudm.afutube.updater.AppUpdate
import com.afudm.afutube.updater.ExtractorUpdater
import com.afudm.afutube.updater.UpdateManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

@Composable
fun SettingsScreen(
    currentVersionCode: Int = 1000000,
    currentVersionName: String = "",
    shareLink: String = "https://github.com/pirncedark/AfuDM/releases",
    onUpdateFound: (AppUpdate) -> Unit = {}
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var ytdlpVersion by remember { mutableStateOf("…") }
    var extractorStatus by remember { mutableStateOf("") }
    var isUpdating by remember { mutableStateOf(false) }
    var extractorAutoUpdate by remember { mutableStateOf(ExtractorUpdater.autoUpdateEnabled(context)) }
    var autoUpdate by remember { mutableStateOf(UpdateManager.autoCheckEnabled(context)) }
    var appUpdateStatus by remember { mutableStateOf("") }
    var preparingApk by remember { mutableStateOf(false) }
    var errorExpanded by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        UpdateManager.setIncludePrereleases(context, false)
        ytdlpVersion = ExtractorUpdater.currentVersion(context)
    }

    Column(Modifier.fillMaxSize()) {
        Text("Ayarlar", color = AfuColors.text, fontSize = 22.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 20.dp, vertical = 16.dp))
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            item {
                SettingsCard("Güncelleme") {
                    Text("Sürüm ${currentVersionName.ifBlank { "—" }}", color = AfuColors.text, fontSize = 14.sp, fontWeight = FontWeight.Medium)
                    Spacer(Modifier.height(10.dp))
                    OutlinedButton(
                        onClick = {
                            scope.launch {
                                appUpdateStatus = "Denetleniyor…"
                                runCatching { UpdateManager.check(currentVersionCode, false) }
                                    .onSuccess { update ->
                                        if (update == null) appUpdateStatus = "Uygulama güncel"
                                        else { appUpdateStatus = "Yeni sürüm bulundu"; onUpdateFound(update) }
                                    }
                                    .onFailure { appUpdateStatus = "Güncelleme denetlenemedi" }
                            }
                        }, modifier = Modifier.fillMaxWidth(), border = BorderStroke(1.dp, AfuColors.accent),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = AfuColors.text)
                    ) { Text("Güncellemeleri denetle") }
                    if (appUpdateStatus.isNotBlank()) Text(appUpdateStatus, color = AfuColors.textMuted, fontSize = 12.sp)
                    SettingSwitch("Açılışta kontrol et", autoUpdate) {
                        autoUpdate = it; UpdateManager.setAutoCheckEnabled(context, it)
                    }
                }
            }
            item {
                SettingsCard("Paylaş") {
                    Text("AfuTube'u arkadaşına gönder", color = AfuColors.text, fontSize = 14.sp)
                    Spacer(Modifier.height(10.dp))
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        OutlinedButton(
                            onClick = { shareText(context, "AfuTube ile video ve müzik indir: $shareLink") },
                            modifier = Modifier.weight(1f), border = BorderStroke(1.dp, AfuColors.accent),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = AfuColors.text)
                        ) { Text("Link gönder", maxLines = 1) }
                        OutlinedButton(
                            onClick = {
                                val appInfo = context.applicationInfo
                                if (!appInfo.splitSourceDirs.isNullOrEmpty()) {
                                    shareText(context, "AfuTube ile video ve müzik indir: $shareLink")
                                    Toast.makeText(context, "Bu kurulumda APK tek dosya değil, link gönderildi", Toast.LENGTH_SHORT).show()
                                } else scope.launch {
                                    preparingApk = true
                                    runCatching { withContext(Dispatchers.IO) { prepareApk(context, currentVersionName) } }
                                        .onSuccess { uri -> shareApk(context, uri) }
                                        .onFailure { Toast.makeText(context, "APK hazırlanamadı", Toast.LENGTH_SHORT).show() }
                                    preparingApk = false
                                }
                            }, enabled = !preparingApk, modifier = Modifier.weight(1f),
                            border = BorderStroke(1.dp, AfuColors.accent), colors = ButtonDefaults.outlinedButtonColors(contentColor = AfuColors.text)
                        ) { Text(if (preparingApk) "Hazırlanıyor…" else "APK gönder", maxLines = 1) }
                    }
                    Text("APK, bu telefondaki sürümdür.", color = AfuColors.textMuted, fontSize = 12.sp, modifier = Modifier.padding(top = 4.dp))
                }
            }
            item {
                SettingsCard("İndirme motoru") {
                    Text("yt-dlp $ytdlpVersion", color = AfuColors.text, fontSize = 14.sp, fontWeight = FontWeight.Medium)
                    if (extractorStatus.isNotBlank()) Text(extractorStatus, color = AfuColors.textMuted, fontSize = 12.sp)
                    Spacer(Modifier.height(8.dp))
                    OutlinedButton(
                        onClick = {
                            scope.launch {
                                isUpdating = true; extractorStatus = "Güncelleniyor…"
                                val channel = ExtractorUpdater.selectedChannel(context)
                                val result = ExtractorUpdater.checkAndUpdate(context, channel, force = true)
                                ytdlpVersion = result.newVersion
                                extractorStatus = if (result.updated) "Motor güncellendi" else if (result.error.isNotBlank()) "Güncelleme başarısız" else "Motor güncel"
                                isUpdating = false
                            }
                        }, enabled = !isUpdating, modifier = Modifier.fillMaxWidth(),
                        border = BorderStroke(1.dp, AfuColors.accent), colors = ButtonDefaults.outlinedButtonColors(contentColor = AfuColors.text)
                    ) { Text(if (isUpdating) "Güncelleniyor…" else "Motoru güncelle") }
                    SettingSwitch("Otomatik güncelle", extractorAutoUpdate) {
                        extractorAutoUpdate = it; ExtractorUpdater.setAutoUpdateEnabled(context, it)
                    }
                }
            }
            LastAnalysisErrorStore.get()?.let { error ->
                item {
                    SettingsCard("Son hata") {
                        TextButton(onClick = { errorExpanded = !errorExpanded }, contentPadding = PaddingValues(0.dp)) {
                            Text(if (errorExpanded) "Detayları gizle" else "Hata ayrıntıları", color = AfuColors.textMuted)
                        }
                        if (errorExpanded) Text(
                            "${error.categoryLabel} · yt-dlp ${error.ytDlpVersion} · ${error.traceback}",
                            color = AfuColors.textMuted, fontSize = 11.sp, maxLines = 8, overflow = TextOverflow.Ellipsis
                        )
                    }
                }
            }
            item {
                Text(
                    "Yalnızca indirme hakkın olan içerikleri indir.", color = AfuColors.textMuted,
                    fontSize = 12.sp, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth().padding(vertical = 10.dp)
                )
            }
        }
    }
}

private fun shareText(context: Context, text: String) {
    val intent = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text)
    startShare(context, intent)
}

private fun shareApk(context: Context, uri: android.net.Uri) {
    val intent = Intent(Intent.ACTION_SEND).setType("application/vnd.android.package-archive")
        .putExtra(Intent.EXTRA_STREAM, uri).putExtra(Intent.EXTRA_TEXT, "AfuTube kurulum dosyası")
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    startShare(context, intent)
}

private fun startShare(context: Context, intent: Intent) {
    val packageManager = context.packageManager
    val whatsapp = listOf("com.whatsapp", "com.whatsapp.w4b").firstOrNull { packageName ->
        runCatching { packageManager.getPackageInfo(packageName, 0) }.isSuccess
    }
    if (whatsapp != null) intent.setPackage(whatsapp)
    try {
        context.startActivity(if (whatsapp == null) Intent.createChooser(intent, "AfuTube'u paylaş") else intent)
    } catch (_: Exception) {
        intent.setPackage(null)
        context.startActivity(Intent.createChooser(intent, "AfuTube'u paylaş"))
    }
}

private fun prepareApk(context: Context, versionName: String): android.net.Uri {
    val directory = File(context.cacheDir, "share")
    directory.mkdirs()
    directory.listFiles()?.forEach { it.delete() }
    val destination = File(directory, "AfuTube-$versionName.apk")
    File(context.applicationInfo.sourceDir).copyTo(destination, overwrite = true)
    return FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", destination)
}

@Composable
private fun SettingSwitch(label: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = AfuColors.text, fontSize = 14.sp)
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}

@Composable
private fun SettingsCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = AfuColors.card), shape = RoundedCornerShape(14.dp)) {
        Column(Modifier.padding(16.dp)) {
            Text(title, color = AfuColors.textMuted, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(10.dp))
            content()
        }
    }
}
