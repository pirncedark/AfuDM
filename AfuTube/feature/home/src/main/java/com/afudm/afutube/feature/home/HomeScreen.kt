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
import com.afudm.afutube.core.extractor.MediaInfo
import com.afudm.afutube.core.theme.AfuColors

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    sharedUrl   : String?    = null,
    onNavigateToFormats: (MediaInfo) -> Unit = {}
) {
    val context = LocalContext.current
    val viewModel = remember(context) { HomeViewModel(context.applicationContext) }
    val state     by viewModel.state.collectAsState()
    val clipboard = LocalClipboardManager.current

    // Share Intent'ten gelen URL'yi otomatik işle
    LaunchedEffect(sharedUrl) {
        if (!sharedUrl.isNullOrBlank()) viewModel.analyzeUrl(sharedUrl)
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

            Spacer(Modifier.height(20.dp))

            // ── Hata mesajı ───────────────────────────────────────────────
            AnimatedVisibility(
                visible = state.error.isNotBlank(),
                enter   = fadeIn() + expandVertically(),
                exit    = fadeOut() + shrinkVertically()
            ) {
                ErrorCard(message = state.error)
            }

            // ── Desteklenen siteler ───────────────────────────────────────
            if (state.url.isBlank() && !state.isLoading) {
                Spacer(Modifier.height(32.dp))
                SupportedSitesBadges()
            }
        }
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
private fun ErrorCard(message: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors   = CardDefaults.cardColors(
            containerColor = AfuColors.error.copy(alpha = 0.12f)
        ),
        shape    = RoundedCornerShape(12.dp)
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(Icons.Default.Warning, null, tint = AfuColors.error, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(10.dp))
            Text(
                text     = message,
                color    = AfuColors.error,
                fontSize = 13.sp,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis
            )
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
