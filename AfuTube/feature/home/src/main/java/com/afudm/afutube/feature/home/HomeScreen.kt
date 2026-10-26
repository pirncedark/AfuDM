package com.afudm.afutube.feature.home

import android.content.Intent
import android.widget.Toast
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.afudm.afutube.core.diagnostics.AnalysisError
import com.afudm.afutube.core.diagnostics.AnalysisErrorCategory
import com.afudm.afutube.core.extractor.InstagramCookies
import com.afudm.afutube.core.extractor.MediaInfo
import com.afudm.afutube.core.extractor.UrlClassifier
import com.afudm.afutube.core.extractor.UrlNormalizer
import com.afudm.afutube.core.extractor.UrlType
import com.afudm.afutube.core.theme.AfuColors
import com.afudm.afutube.core.ui.InstagramLoginDialog

data class SharedLinkEvent(val url: String?)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    sharedUrl   : String?    = null,
    sharedEventId: Long?     = null,
    sharedLinkReady: Boolean = true,
    onConsumeShareEvent: (Long) -> SharedLinkEvent? = { null },
    onNavigateToFormats: (MediaInfo) -> Unit = {},
    onOpenBrowser: (String) -> Unit = {},
    onUpdateExtractor: () -> Unit = {}
) {
    val context = LocalContext.current
    val viewModel = remember(context) { HomeViewModel(context.applicationContext) }
    val state     by viewModel.state.collectAsState()
    val clipboard = LocalClipboardManager.current
    var showInstagramLogin by remember { mutableStateOf(false) }

    if (showInstagramLogin) {
        InstagramLoginDialog(
            onDismiss = { showInstagramLogin = false },
            onLoginSuccess = {
                showInstagramLogin = false
                viewModel.analyzeUrl(state.url)
            }
        )
    }

    // Share Intent'ten gelen URL'yi otomatik işle
    LaunchedEffect(sharedEventId, sharedLinkReady) {
        if (!sharedLinkReady) return@LaunchedEffect
        val event = sharedEventId?.let(onConsumeShareEvent)
        if (event?.url != null) {
            val normalizedUrl = UrlNormalizer.normalize(event.url) ?: event.url
            viewModel.onUrlChange(normalizedUrl)
            viewModel.analyzeUrl(normalizedUrl)
        } else if (event != null) {
            viewModel.onUrlChange("")
            Toast.makeText(context, "Paylaşılan metinde bağlantı bulunamadı", Toast.LENGTH_SHORT).show()
        } else if (sharedEventId == null && !sharedUrl.isNullOrBlank()) {
            val normalizedUrl = UrlNormalizer.normalize(sharedUrl) ?: sharedUrl
            viewModel.onUrlChange(normalizedUrl)
            viewModel.analyzeUrl(normalizedUrl)
        }
    }

    // Format sonucu gelince format ekranına geç
    LaunchedEffect(state.mediaInfo) {
        state.mediaInfo?.let {
            onNavigateToFormats(it)
            viewModel.consumeMediaInfo(it)
        }
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
                onOpenBrowser = { onOpenBrowser(state.url) },
                isLoading   = state.isLoading
            )

            Spacer(Modifier.height(20.dp))

            // ── Hata mesajı ───────────────────────────────────────────────
            AnimatedVisibility(
                visible = state.error.isNotBlank(),
                enter   = fadeIn() + expandVertically(),
                exit    = fadeOut() + shrinkVertically()
            ) {
                ErrorCard(
                    url = state.url,
                    error = state.analysisError,
                    onRetry = { viewModel.analyzeUrl(state.url) },
                    onUpdate = onUpdateExtractor,
                    onOpenBrowser = { onOpenBrowser(state.url) },
                    onOpenLogin = { showInstagramLogin = true }
                )
            }

            // ── Desteklenen siteler ───────────────────────────────────────
            if (state.url.isBlank() && !state.isLoading) {
                Spacer(Modifier.height(32.dp))
                Text("YouTube, Instagram, TikTok ve 1800+ site", color = AfuColors.textMuted, fontSize = 12.sp)
            }
        }
    }
}

@Composable
private fun AfuTubeLogo() {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text("AfuTube", fontSize = 27.sp, fontWeight = FontWeight.SemiBold, color = AfuColors.text)
        Spacer(Modifier.height(6.dp))
        Text("Linki yapıştır, gerisini AfuTube halleder.", fontSize = 13.sp, color = AfuColors.textMuted)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun UrlInputCard(
    url         : String,
    onUrlChange : (String) -> Unit,
    onPaste     : () -> Unit,
    onAnalyze   : () -> Unit,
    onOpenBrowser: () -> Unit,
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
                    unfocusedBorderColor = AfuColors.textMuted.copy(alpha = 0.3f),
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
                    contentPadding = PaddingValues(horizontal = 8.dp),
                    colors  = ButtonDefaults.outlinedButtonColors(contentColor = AfuColors.textMuted),
                    border  = androidx.compose.foundation.BorderStroke(1.dp, AfuColors.textMuted.copy(alpha = 0.3f))
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
                        containerColor = AfuColors.surface,
                        contentColor   = AfuColors.text,
                        disabledContainerColor = AfuColors.surface,
                        disabledContentColor = AfuColors.textMuted
                    ),
                    border = androidx.compose.foundation.BorderStroke(1.dp, AfuColors.accent),
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
            OutlinedButton(
                onClick = onOpenBrowser,
                enabled = url.isNotBlank(),
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = AfuColors.textMuted),
                border = BorderStroke(1.dp, AfuColors.textMuted.copy(alpha = 0.3f)),
                shape = RoundedCornerShape(10.dp)
            ) { Text("Tarayıcıda aç") }
        }
    }
}

@Composable
private fun ErrorCard(
    url: String,
    error: AnalysisError?,
    onRetry: () -> Unit,
    onUpdate: () -> Unit,
    onOpenBrowser: () -> Unit,
    onOpenLogin: () -> Unit
) {
    if (error == null) return
    val clipboard = LocalClipboardManager.current
    var detailsVisible by remember { mutableStateOf(false) }
    val isLoginRequired = error.category == AnalysisErrorCategory.LOGIN_REQUIRED
    val isInstagram = InstagramCookies.isInstagram(url) || UrlClassifier.classify(url) == UrlType.INSTAGRAM

    val title = when {
        isLoginRequired && isInstagram -> "Bu Instagram içeriği için giriş yapılması gerekiyor."
        isLoginRequired -> "Bu içeriği indirmek için oturum açılması gerekiyor."
        isInstagram -> "Instagram içeriği analiz edilemedi."
        UrlClassifier.isYouTubeHost(url) -> "YouTube videosu analiz edilemedi."
        UrlClassifier.classify(url) == UrlType.TIKTOK -> "TikTok videosu analiz edilemedi."
        UrlClassifier.classify(url) == UrlType.TWITTER_X -> "X (Twitter) videosu analiz edilemedi."
        else -> "İçerik analiz edilemedi."
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors   = CardDefaults.cardColors(
            containerColor = AfuColors.bg
        ),
        shape    = RoundedCornerShape(12.dp),
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            if (isLoginRequired) AfuColors.accent.copy(alpha = 0.7f) else AfuColors.error.copy(alpha = 0.7f)
        )
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    if (isLoginRequired) Icons.Default.Lock else Icons.Default.Warning,
                    null,
                    tint = if (isLoginRequired) AfuColors.accent else AfuColors.error,
                    modifier = Modifier.size(20.dp)
                )
                Spacer(Modifier.width(10.dp))
                Text(
                    analysisErrorDisplayMessage(isLoginRequired, isInstagram, title),
                    color = if (isLoginRequired) AfuColors.text else AfuColors.error,
                    fontSize = 13.sp,
                    fontWeight = if (isLoginRequired) FontWeight.Medium else FontWeight.Normal
                )
            }
            Spacer(Modifier.height(10.dp))
            if (isLoginRequired) {
                Button(
                    onClick = onOpenLogin,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = AfuColors.accent),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Icon(Icons.Default.Lock, null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(if (isInstagram) "Instagram'a Giriş Yap" else "Giriş Yap")
                }
                Spacer(Modifier.height(6.dp))
                OutlinedButton(
                    onClick = onRetry,
                    modifier = Modifier.fillMaxWidth(),
                    border = BorderStroke(1.dp, AfuColors.textMuted.copy(alpha = 0.3f)),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Text("Tekrar dene", color = AfuColors.text)
                }
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = onUpdate, modifier = Modifier.weight(1f)) { Text("Motoru güncelle") }
                    OutlinedButton(onClick = onRetry, modifier = Modifier.weight(1f)) { Text("Tekrar dene") }
                }
            }
            OutlinedButton(
                onClick = onOpenBrowser,
                modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = AfuColors.textMuted),
                border = BorderStroke(1.dp, AfuColors.textMuted.copy(alpha = 0.3f)),
                shape = RoundedCornerShape(10.dp)
            ) { Text("Tarayıcıda aç ve videoyu yakala") }
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

internal fun analysisErrorDisplayMessage(isLoginRequired: Boolean, isInstagram: Boolean, title: String): String =
    if (isLoginRequired && isInstagram) "Instagram'a giriş gerekli. Ayarlar'dan giriş yap." else title
