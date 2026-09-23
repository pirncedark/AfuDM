package com.afudm.afutube.feature.home

import android.content.Intent
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.afudm.afutube.core.diagnostics.AnalysisError
import com.afudm.afutube.core.extractor.MediaInfo
import com.afudm.afutube.core.extractor.UrlNormalizer
import com.afudm.afutube.core.theme.AfuColors
import com.afudm.afutube.downloader.DownloadEngine
import com.afudm.afutube.downloader.DownloadPolicies

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    sharedUrl   : String?    = null,
    sharedEventId: Long?     = null,
    sharedUrls: List<String>? = null,
    onNavigateToFormats: (MediaInfo) -> Unit = {},
    onUpdateExtractor: () -> Unit = {}
) {
    val context = LocalContext.current
    val viewModel = remember(context) { HomeViewModel(context.applicationContext) }
    val state     by viewModel.state.collectAsState()
    val clipboard = LocalClipboardManager.current
    var collectedLinks by remember { mutableStateOf(emptyList<String>()) }
    var selectedLinks by remember { mutableStateOf(emptySet<String>()) }

    // Share Intent'ten gelen URL'yi otomatik işle
    LaunchedEffect(sharedEventId) {
        val urls = sharedUrls.orEmpty().ifEmpty { listOfNotNull(sharedUrl) }
        if (urls.size > 1) {
            collectedLinks = urls
            selectedLinks = urls.toSet()
        } else if (urls.isNotEmpty()) {
            val normalizedUrl = UrlNormalizer.normalize(urls.first()) ?: urls.first()
            viewModel.onUrlChange(normalizedUrl)
            viewModel.analyzeUrl(normalizedUrl)
        }
    }

    // Format sonucu gelince format ekranına geç
    LaunchedEffect(state.mediaInfo) {
        state.mediaInfo?.let { onNavigateToFormats(it) }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(AfuColors.bg)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Spacer(Modifier.height(56.dp))

            // ── Logo / Başlık ──────────────────────────────────────────────
            AfuTubeLogo()

            Spacer(Modifier.height(40.dp))

            // ── URL Giriş Kartı ───────────────────────────────────────────
            UrlInputCard(
                url         = state.url,
                onUrlChange = viewModel::onUrlChange,
                onPaste     = {
                    val clip = clipboard.getText()?.text ?: ""
                    viewModel.onUrlChange(clip)
                },
                onAnalyze   = { viewModel.analyzeUrl(state.url) },
                isLoading   = state.isLoading
            )

            OutlinedButton(onClick = {
                val text = clipboard.getText()?.text.orEmpty()
                collectedLinks = DownloadPolicies.extractHttpLinks(text)
                selectedLinks = collectedLinks.toSet()
            }, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.Link, null)
                Spacer(Modifier.width(8.dp))
                Text(context.getString(R.string.collect_links))
            }

            Spacer(Modifier.height(20.dp))

            // ── Hata mesajı ───────────────────────────────────────────────
            AnimatedVisibility(
                visible = state.error.isNotBlank(),
                enter   = fadeIn() + expandVertically(),
                exit    = fadeOut() + shrinkVertically()
            ) {
                ErrorCard(
                    error = state.analysisError,
                    onRetry = { viewModel.analyzeUrl(state.url) },
                    onUpdate = onUpdateExtractor
                )
            }

            // ── Desteklenen siteler ───────────────────────────────────────
            if (state.url.isBlank() && !state.isLoading) {
                Spacer(Modifier.height(32.dp))
                SupportedSitesBadges()
            }
        }
    }

    if (collectedLinks.isNotEmpty()) {
        AlertDialog(
            onDismissRequest = { collectedLinks = emptyList() },
            title = { Text(context.getString(R.string.collected_links_title)) },
            text = {
                Column {
                    collectedLinks.forEach { link ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = link in selectedLinks, onCheckedChange = { checked ->
                                selectedLinks = if (checked) selectedLinks + link else selectedLinks - link
                            })
                            Text(link, maxLines = 2, overflow = TextOverflow.Ellipsis, color = AfuColors.text)
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    selectedLinks.forEach { link ->
                        DownloadEngine.getInstance(context).enqueue(
                            DownloadEngine.DownloadRequest(url = link, title = link.substringAfter("//").take(48))
                        )
                    }
                    collectedLinks = emptyList()
                }, enabled = selectedLinks.isNotEmpty()) { Text(context.getString(R.string.queue_selected_links)) }
            },
            dismissButton = { TextButton(onClick = { collectedLinks = emptyList() }) { Text(context.getString(R.string.cancel)) } }
        )
    }
}

@Composable
private fun AfuTubeLogo() {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        // Gradient ikon çemberi
        Box(
            modifier = Modifier
                .size(72.dp)
                .clip(RoundedCornerShape(20.dp))
                .background(
                    Brush.linearGradient(
                        listOf(AfuColors.accent, AfuColors.accentAlt)
                    )
                ),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Default.Download,
                contentDescription = null,
                tint = Color.White,
                modifier = Modifier.size(36.dp)
            )
        }
        Spacer(Modifier.height(12.dp))
        Text(
            text = "AfuTube",
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold,
            color = AfuColors.text
        )
        Text(
            text = "Medya İndirme Motoru",
            fontSize = 13.sp,
            color = AfuColors.textMuted
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun UrlInputCard(
    url         : String,
    onUrlChange : (String) -> Unit,
    onPaste     : () -> Unit,
    onAnalyze   : () -> Unit,
    isLoading   : Boolean
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors   = CardDefaults.cardColors(containerColor = AfuColors.card),
        shape    = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text  = "Video veya ses URL'si yapıştır",
                color = AfuColors.textMuted,
                fontSize = 12.sp
            )
            Spacer(Modifier.height(8.dp))

            OutlinedTextField(
                value           = url,
                onValueChange   = onUrlChange,
                placeholder     = { Text("https://...", color = AfuColors.textMuted) },
                modifier        = Modifier.fillMaxWidth(),
                singleLine      = true,
                colors          = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor   = AfuColors.accent,
                    unfocusedBorderColor = AfuColors.surface,
                    focusedTextColor     = AfuColors.text,
                    unfocusedTextColor   = AfuColors.text,
                    cursorColor          = AfuColors.accent
                ),
                shape           = RoundedCornerShape(10.dp),
                trailingIcon    = {
                    if (url.isNotBlank()) {
                        IconButton(onClick = { onUrlChange("") }) {
                            Icon(Icons.Default.Close, null, tint = AfuColors.textMuted)
                        }
                    }
                }
            )

            Spacer(Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                // Yapıştır butonu
                OutlinedButton(
                    onClick = onPaste,
                    modifier = Modifier.weight(1f),
                    colors  = ButtonDefaults.outlinedButtonColors(contentColor = AfuColors.accent),
                    border  = androidx.compose.foundation.BorderStroke(1.dp, AfuColors.accent.copy(alpha = 0.4f))
                ) {
                    Icon(Icons.Default.ContentPaste, null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Yapıştır")
                }

                // Analiz butonu
                Button(
                    onClick  = onAnalyze,
                    enabled  = url.isNotBlank() && !isLoading,
                    modifier = Modifier.weight(1.5f),
                    colors   = ButtonDefaults.buttonColors(
                        containerColor = AfuColors.accent,
                        contentColor   = Color.White
                    ),
                    shape    = RoundedCornerShape(10.dp)
                ) {
                    if (isLoading) {
                        CircularProgressIndicator(
                            modifier  = Modifier.size(16.dp),
                            color     = Color.White,
                            strokeWidth = 2.dp
                        )
                        Spacer(Modifier.width(8.dp))
                        Text("Analiz ediliyor…")
                    } else {
                        Icon(Icons.Default.Search, null, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("Analiz Et")
                    }
                }
            }
        }
    }
}

@Composable
private fun ErrorCard(
    error: AnalysisError?,
    onRetry: () -> Unit,
    onUpdate: () -> Unit
) {
    if (error == null) return
    val clipboard = LocalClipboardManager.current
    var detailsVisible by remember { mutableStateOf(false) }
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors   = CardDefaults.cardColors(
            containerColor = AfuColors.error.copy(alpha = 0.12f)
        ),
        shape    = RoundedCornerShape(12.dp)
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Warning, null, tint = AfuColors.error, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(10.dp))
                Text("YouTube videosu analiz edilemedi.", color = AfuColors.error, fontSize = 13.sp)
            }
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = onUpdate, modifier = Modifier.weight(1f)) { Text("Motoru güncelle") }
                OutlinedButton(onClick = onRetry, modifier = Modifier.weight(1f)) { Text("Tekrar dene") }
            }
            TextButton(onClick = { detailsVisible = !detailsVisible }) {
                Text(if (detailsVisible) "Detayları gizle" else "Detaylar >")
            }
            if (detailsVisible) {
                Text("${error.categoryLabel} · yt-dlp ${error.ytDlpVersion} · exit ${error.exitCode ?: "yok"}", color = AfuColors.textMuted, fontSize = 11.sp)
                Spacer(Modifier.height(6.dp))
                Text(error.traceback, color = AfuColors.textMuted, fontSize = 11.sp, maxLines = 12, overflow = TextOverflow.Ellipsis)
                TextButton(onClick = { clipboard.setText(androidx.compose.ui.text.AnnotatedString(error.copyText())) }) {
                    Icon(Icons.Default.ContentCopy, null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("Kopyala")
                }
            }
        }
    }
}

@Composable
private fun SupportedSitesBadges() {
    val sites = listOf(
        "YouTube" to Icons.Default.PlayCircle,
        "Instagram" to Icons.Default.CameraAlt,
        "TikTok" to Icons.Default.MusicNote,
        "Twitter/X" to Icons.Default.Tag,
        "Facebook" to Icons.Default.Public,
        "+1800 site" to Icons.Default.Language
    )
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text("Desteklenen Platformlar", color = AfuColors.textMuted, fontSize = 12.sp)
        Spacer(Modifier.height(12.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically
        ) {
            sites.chunked(3).forEach { row ->
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    row.forEach { (name, icon) ->
                        SiteBadge(name = name, icon = icon)
                    }
                }
                Spacer(Modifier.width(16.dp))
            }
        }
    }
}

@Composable
private fun SiteBadge(name: String, icon: androidx.compose.ui.graphics.vector.ImageVector) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .background(AfuColors.card)
            .padding(horizontal = 10.dp, vertical = 6.dp)
    ) {
        Icon(icon, null, tint = AfuColors.accent, modifier = Modifier.size(14.dp))
        Spacer(Modifier.width(6.dp))
        Text(name, color = AfuColors.text, fontSize = 12.sp)
    }
}
