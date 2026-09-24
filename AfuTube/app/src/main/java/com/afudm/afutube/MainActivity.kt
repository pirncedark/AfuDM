package com.afudm.afutube

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.lifecycle.ViewModelProvider
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.compose.*
import com.afudm.afutube.core.extractor.MediaInfo
import com.afudm.afutube.feature.downloads.DownloadsScreen
import com.afudm.afutube.feature.formats.FormatPickerScreen
import com.afudm.afutube.core.theme.AfuColors
import com.afudm.afutube.feature.home.HomeScreen
import com.afudm.afutube.feature.home.SharedLinkEvent
import com.afudm.afutube.feature.settings.SettingsScreen
import com.afudm.afutube.feature.torrent.TorrentPickerScreen
import com.afudm.afutube.updater.AppUpdate
import com.afudm.afutube.updater.UpdateManager
import com.afudm.afutube.runtime.MediaRuntime
import com.afudm.afutube.downloader.DownloadEngine
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private val shareViewModel by lazy { ViewModelProvider(this)[ShareIntentViewModel::class.java] }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        shareViewModel.publish(intent)

        setContent { AfuTubeApp(shareViewModel) }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        shareViewModel.publish(intent)
    }
}

// ── Navigation ────────────────────────────────────────────────────────────────

sealed class Screen(val route: String, val label: String, val icon: ImageVector) {
    object Home      : Screen("home",      "Ana Ekran",   Icons.Default.Home)
    object Torrent   : Screen("torrent",   "Torrent",     Icons.Default.MoveToInbox)
    object Downloads : Screen("downloads", "İndirmeler",  Icons.Default.Download)
    object Settings  : Screen("settings",  "Ayarlar",     Icons.Default.Settings)
}

@Composable
fun AfuTubeApp(shareViewModel: ShareIntentViewModel) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val runtimeStatus by MediaRuntime.status.collectAsState()
    val shareEvent by shareViewModel.events.collectAsState()
    val runtimeScope = rememberCoroutineScope()

    if (runtimeStatus.state != MediaRuntime.RuntimeState.READY && shareEvent == null) {
        MotorReadinessScreen(
            status = runtimeStatus,
            onRetry = { runtimeScope.launch { RuntimeBootstrap.prepare(context) } }
        )
        return
    }

    val navController     = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute      = navBackStackEntry?.destination?.route

    var pendingMediaInfo by remember { mutableStateOf<MediaInfo?>(null) }
    var browserUrl by remember { mutableStateOf("") }
    var routedShareSequence by remember { mutableLongStateOf(0L) }
    var availableUpdate by remember { mutableStateOf<AppUpdate?>(null) }
    LaunchedEffect(shareEvent?.sequence) {
        val event = shareEvent ?: return@LaunchedEffect
        if (event.sequence <= routedShareSequence) return@LaunchedEffect
        routedShareSequence = event.sequence
        pendingMediaInfo = null
        if (currentRoute != null && currentRoute != Screen.Home.route) {
            navController.navigate(Screen.Home.route) {
                popUpTo(Screen.Home.route) { inclusive = false }
                launchSingleTop = true
            }
        }
    }
    LaunchedEffect(Unit) {
        if (UpdateManager.shouldCheckAutomatically(context)) {
            UpdateManager.markChecked(context)
            runCatching { UpdateManager.check(BuildConfig.VERSION_CODE, UpdateManager.includePrereleases(context)) }.getOrNull()?.let { availableUpdate = it }
        }
    }

    // Android 13+: indirme bitince "Kurmak icin dokun" bildirimi gorunebilsin diye izin iste.
    val notificationPermission = androidx.activity.compose.rememberLauncherForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.RequestPermission()
    ) { }

    availableUpdate?.let { update ->
        AlertDialog(
            onDismissRequest = { availableUpdate = null },
            title = { Text("Yeni AfuTube surumu bulundu") },
            text = { Text("Surum: ${update.versionName}\n\n${update.releaseNotes.ifBlank { "Yeni hata duzeltmeleri ve gelistirmeler." }}") },
            confirmButton = { TextButton(onClick = {
                availableUpdate = null
                if (android.os.Build.VERSION.SDK_INT >= 33 &&
                    context.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED
                ) notificationPermission.launch(android.Manifest.permission.POST_NOTIFICATIONS)
                UpdateManager.enqueueDownload(context, update)
                android.widget.Toast.makeText(context, "Güncelleme indiriliyor — bildirimden takip edebilirsin", android.widget.Toast.LENGTH_LONG).show()
            }) { Text("Indir ve kur") } },
            dismissButton = { TextButton(onClick = { availableUpdate = null }) { Text("Daha sonra") } }
        )
    }

    val bottomScreens = listOf(Screen.Home, Screen.Torrent, Screen.Downloads, Screen.Settings)
    val showBottomBar = currentRoute in bottomScreens.map { it.route }

    Scaffold(
        containerColor = AfuColors.bg,
        bottomBar = {
            if (showBottomBar) {
                AfuBottomBar(
                    screens      = bottomScreens,
                    currentRoute = currentRoute,
                    onNavigate   = { navController.navigate(it) { launchSingleTop = true } }
                )
            }
        }
    ) { padding ->
        NavHost(
            navController    = navController,
            startDestination = Screen.Home.route,
            modifier         = Modifier.padding(padding)
        ) {
            composable(Screen.Home.route) {
                HomeScreen(
                    sharedUrl = shareEvent?.url,
                    sharedEventId = shareEvent?.sequence,
                    sharedLinkReady = runtimeStatus.state == MediaRuntime.RuntimeState.READY,
                    onConsumeShareEvent = { sequence -> shareViewModel.consume(sequence)?.let { SharedLinkEvent(it.url) } },
                    onNavigateToFormats = { info ->
                        pendingMediaInfo = info
                        navController.navigate("formats")
                    },
                    onOpenBrowser = { url ->
                        browserUrl = url.trim()
                        if (browserUrl.isNotBlank()) navController.navigate("browser")
                    }
                )
            }
            composable("browser") {
                BrowserScreen(
                    startUrl = browserUrl,
                    onClose = { navController.popBackStack() },
                    onDownload = { DownloadEngine.getInstance(context).enqueue(it) }
                )
            }
            composable("formats") {
                pendingMediaInfo?.let { info ->
                    FormatPickerScreen(
                        mediaInfo  = info,
                        onBack     = { navController.popBackStack() },
                        onDownload = { navController.navigate(Screen.Downloads.route) { launchSingleTop = true } }
                    )
                }
            }
            composable(Screen.Downloads.route) { DownloadsScreen() }
            composable(Screen.Settings.route)  {
                SettingsScreen(currentVersionCode = BuildConfig.VERSION_CODE, currentVersionName = BuildConfig.VERSION_NAME, shareLink = ShareLinkBuilder.url(BuildConfig.VERSION_NAME), onUpdateFound = { availableUpdate = it })
            }
            composable(Screen.Torrent.route)   {
                TorrentPickerScreen(onBack = { navController.popBackStack() })
            }
        }
    }
}

@Composable
private fun MotorReadinessScreen(
    status: MediaRuntime.RuntimeStatus,
    onRetry: () -> Unit
) {
    var detailsVisible by remember { mutableStateOf(false) }
    Box(
        modifier = Modifier.fillMaxSize().background(AfuColors.bg),
        contentAlignment = androidx.compose.ui.Alignment.Center
    ) {
        Column(
            modifier = Modifier.padding(28.dp),
            horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = if (status.state == MediaRuntime.RuntimeState.FAILED) Icons.Default.Warning else Icons.Default.Download,
                contentDescription = null,
                tint = if (status.state == MediaRuntime.RuntimeState.FAILED) AfuColors.error else AfuColors.accent,
                modifier = Modifier.size(52.dp)
            )
            Spacer(Modifier.height(18.dp))
            Text(
                text = if (status.state == MediaRuntime.RuntimeState.FAILED) "Medya motoru hazırlanamadı" else "Motor hazırlanıyor",
                color = AfuColors.text,
                style = MaterialTheme.typography.titleLarge
            )
            Spacer(Modifier.height(10.dp))
            Text(
                text = if (status.state == MediaRuntime.RuntimeState.FAILED) {
                    "yt-dlp, FFmpeg ve aria2 başlatılamadı."
                } else {
                    "Python, yt-dlp, FFmpeg ve aria2 kontrol ediliyor."
                },
                color = AfuColors.textMuted
            )
            if (status.state != MediaRuntime.RuntimeState.FAILED) {
                Spacer(Modifier.height(20.dp))
                CircularProgressIndicator(color = AfuColors.accent)
            } else {
                Spacer(Modifier.height(20.dp))
                Button(onClick = onRetry) { Text("Tekrar dene") }
            }
            if (status.details.isNotBlank()) {
                TextButton(onClick = { detailsVisible = !detailsVisible }) {
                    Text(if (detailsVisible) "Detayları gizle" else "Detaylar >")
                }
                if (detailsVisible) {
                    Text(status.details, color = AfuColors.textMuted, fontSize = 11.sp)
                }
            }
        }
    }
}

@Composable
private fun AfuBottomBar(
    screens      : List<Screen>,
    currentRoute : String?,
    onNavigate   : (String) -> Unit
) {
    NavigationBar(
        containerColor = AfuColors.card,
        modifier       = Modifier.clip(RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp))
    ) {
        screens.forEach { screen ->
            val selected = currentRoute == screen.route
            NavigationBarItem(
                selected = selected,
                onClick  = { onNavigate(screen.route) },
                icon     = {
                    Column(horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally) {
                        Icon(screen.icon, contentDescription = screen.label, modifier = Modifier.size(22.dp))
                        if (selected) Spacer(Modifier.width(18.dp).height(1.dp).border(1.dp, AfuColors.accent))
                    }
                },
                label    = { Text(screen.label, fontSize = 10.sp) },
                colors   = NavigationBarItemDefaults.colors(
                    selectedIconColor   = AfuColors.accent,
                    selectedTextColor   = AfuColors.textMuted,
                    indicatorColor      = AfuColors.card,
                    unselectedIconColor = AfuColors.textMuted,
                    unselectedTextColor = AfuColors.textMuted
                )
            )
        }
    }
}
