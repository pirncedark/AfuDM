package com.afudm.afutube.feature.settings

import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
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
import com.afudm.afutube.core.share.ShareHelper
import com.afudm.afutube.core.stats.ActiveUserStats
import com.afudm.afutube.core.stats.activeUserStats
import com.afudm.afutube.core.diagnostics.LastAnalysisErrorStore
import com.afudm.afutube.core.theme.AfuColors
import com.afudm.afutube.core.ui.InstagramLoginDialog
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
    var showInstagramLogin by remember { mutableStateOf(false) }

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
                                        UpdateManager.markChecked(context)
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
                            onClick = { ShareHelper.shareText(context, "AfuTube ile video ve müzik indir: $shareLink") },
                            modifier = Modifier.weight(1f), border = BorderStroke(1.dp, AfuColors.accent),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = AfuColors.text)
                        ) { Text("Link gönder", maxLines = 1) }
                        OutlinedButton(
                            onClick = {
                                val appInfo = context.applicationInfo
                                if (!appInfo.splitSourceDirs.isNullOrEmpty()) {
                                    ShareHelper.shareText(context, "AfuTube ile video ve müzik indir: $shareLink")
                                    Toast.makeText(context, "Bu kurulumda APK tek dosya değil, link gönderildi", Toast.LENGTH_SHORT).show()
                                } else scope.launch {
                                    preparingApk = true
                                    runCatching { withContext(Dispatchers.IO) { prepareApk(context, currentVersionName) } }
                                        .onSuccess { uri -> ShareHelper.shareFile(context, uri, "AfuTube'u paylaş", "AfuTube kurulum dosyası") }
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
            item {
                SettingsCard("Instagram Hesabı") {
                    var hasIgSession by remember { mutableStateOf(com.afudm.afutube.core.extractor.InstagramCookies.hasSession()) }
                    if (showInstagramLogin) {
                        InstagramLoginDialog(
                            onDismiss = { showInstagramLogin = false },
                            onLoginSuccess = {
                                showInstagramLogin = false
                                hasIgSession = true
                                Toast.makeText(context, "Instagram oturumu açıldı", Toast.LENGTH_SHORT).show()
                            }
                        )
                    }
                    if (hasIgSession) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.CheckCircle, null, tint = AfuColors.success, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text("Oturum açık (Hikaye ve özel içerikler erişilebilir)", color = AfuColors.text, fontSize = 13.sp)
                        }
                        Spacer(Modifier.height(10.dp))
                        OutlinedButton(
                            onClick = {
                                com.afudm.afutube.core.extractor.InstagramCookies.clearSession(context)
                                hasIgSession = false
                                Toast.makeText(context, "Instagram oturumu kapatıldı", Toast.LENGTH_SHORT).show()
                            },
                            modifier = Modifier.fillMaxWidth(),
                            border = BorderStroke(1.dp, AfuColors.error.copy(alpha = 0.5f)),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = AfuColors.error)
                        ) { Text("Oturumu Kapat") }
                    } else {
                        Text(
                            "Giriş yapılmadı. Hikaye ve özel içerikleri indirmek için giriş yap.",
                            color = AfuColors.textMuted,
                            fontSize = 13.sp
                        )
                        Spacer(Modifier.height(8.dp))
                        Button(
                            onClick = { showInstagramLogin = true },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(containerColor = AfuColors.accent)
                        ) { Text("Instagram'a giriş yap") }
                    }
                }
            }
            item {
                SettingsCard("Topluluk") {
                    val sayac = remember { activeUserStats(context, currentVersionName) }
                    var sayacOn by remember { mutableStateOf(sayac.enabled) }
                    var sayacStats by remember { mutableStateOf<ActiveUserStats.Stats?>(null) }
                    var sayacLoading by remember { mutableStateOf(false) }
                    LaunchedEffect(sayacOn) {
                        sayacStats = null
                        if (sayacOn) {
                            sayacLoading = true
                            sayacStats = sayac.fetchStats()
                            sayacLoading = false
                        }
                    }
                    if (sayacOn && sayacLoading) {
                        Text("Son 7 günde … kişi AfuTube kullandı", color = AfuColors.textMuted, fontSize = 13.sp)
                    }
                    sayacStats?.let {
                        Text("Son 7 günde ${it.aktif7} kişi AfuTube kullandı", color = AfuColors.text, fontSize = 14.sp)
                    }
                    Spacer(Modifier.height(8.dp))
                    SettingSwitch("Sayaca katıl", sayacOn) { checked ->
                        sayac.enabled = checked
                        sayacOn = checked
                        if (checked) scope.launch { sayac.pingIfNeeded() }
                    }
                    Text(
                        "Yalnız rastgele bir numara gönderilir; ad, konum veya hesap bilgisi gitmez.",
                        color = AfuColors.textMuted, fontSize = 11.sp
                    )
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
            item {
                SettingsCard("Lisanslar") {
                    var licensesExpanded by remember { mutableStateOf(false) }
                    Text("Edit sekmesi WizardCut (MIT) ve FFmpegKit (LGPL) kullanır.", color = AfuColors.text, fontSize = 13.sp)
                    TextButton(onClick = { licensesExpanded = !licensesExpanded }, contentPadding = PaddingValues(0.dp)) {
                        Text(if (licensesExpanded) "Lisansları gizle" else "Açık kaynak lisansları", color = AfuColors.textMuted)
                    }
                    if (licensesExpanded) {
                        val licenseText = remember { openSourceLicenseText(context) }
                        Text(licenseText, color = AfuColors.textMuted, fontSize = 11.sp)
                    }
                }
            }
        }
    }
}

/** WizardCut MIT + NOTICE (assets) ve FFmpegKitNext LGPL kaynak teklifi (wizardcut res/raw). */
private fun openSourceLicenseText(context: Context): String {
    fun asset(name: String) = runCatching { context.assets.open("lisanslar/$name").bufferedReader().use { it.readText() } }.getOrDefault("")
    val sourceOfferId = context.resources.getIdentifier("ffmpeg_kit_next_source_offer", "raw", context.packageName)
    val sourceOffer = if (sourceOfferId == 0) "" else runCatching {
        context.resources.openRawResource(sourceOfferId).bufferedReader().use { it.readText() }
    }.getOrDefault("")
    return listOf(
        "WizardCut — BigWizard Media (ClearCut, SysAdminDoc fork'u)\nhttps://github.com/BigWizard94/wizardcut\n\n" + asset("wizardcut-LICENSE.txt"),
        asset("wizardcut-NOTICE.txt"),
        "FFmpegKitNext / FFmpeg — LGPL-3.0-or-later kaynak teklifi\n\n$sourceOffer",
    ).filter { it.isNotBlank() }.joinToString("\n\n────────\n\n")
}

private fun prepareApk(context: Context, versionName: String): android.net.Uri {
    val directory = File(context.cacheDir, "share")
    directory.mkdirs()
    directory.listFiles()?.forEach { it.delete() }
    val destination = File(directory, "AfuTube-$versionName.apk")
    File(context.applicationInfo.sourceDir).copyTo(destination, overwrite = true)
    return ShareHelper.createShareUri(context, destination)
}

@Composable
private fun SettingSwitch(label: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = AfuColors.text, fontSize = 14.sp)
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = SwitchDefaults.colors(
                checkedThumbColor = AfuColors.text,
                checkedTrackColor = AfuColors.surface,
                checkedBorderColor = AfuColors.accent,
                uncheckedThumbColor = AfuColors.textMuted,
                uncheckedTrackColor = AfuColors.surface,
                uncheckedBorderColor = AfuColors.textMuted.copy(alpha = 0.3f)
            )
        )
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
