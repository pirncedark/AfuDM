package com.afudm.afutube

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
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
import com.afudm.afutube.feature.settings.SettingsScreen
import com.afudm.afutube.feature.torrent.TorrentPickerScreen

class MainActivity : ComponentActivity() {

    private var sharedUrl: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        sharedUrl = extractUrlFromIntent(intent)

        setContent { AfuTubeApp(sharedUrl) }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        sharedUrl = extractUrlFromIntent(intent)
    }

    private fun extractUrlFromIntent(intent: Intent?): String? {
        if (intent?.action != Intent.ACTION_SEND) return null
        if (intent.type != "text/plain") return null
        return intent.getStringExtra(Intent.EXTRA_TEXT)
            ?.trim()?.takeIf { it.startsWith("http") }
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
fun AfuTubeApp(sharedUrl: String? = null) {
    val navController     = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute      = navBackStackEntry?.destination?.route

    var pendingMediaInfo by remember { mutableStateOf<MediaInfo?>(null) }

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
                    sharedUrl = sharedUrl,
                    onNavigateToFormats = { info ->
                        pendingMediaInfo = info
                        navController.navigate("formats")
                    }
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
            composable(Screen.Settings.route)  { SettingsScreen() }
            composable(Screen.Torrent.route)   {
                TorrentPickerScreen(onBack = { navController.popBackStack() })
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
                    Icon(
                        screen.icon,
                        contentDescription = screen.label,
                        modifier = Modifier.size(22.dp)
                    )
                },
                label    = { Text(screen.label, fontSize = 10.sp) },
                colors   = NavigationBarItemDefaults.colors(
                    selectedIconColor   = AfuColors.accent,
                    selectedTextColor   = AfuColors.accent,
                    indicatorColor      = AfuColors.accent.copy(alpha = 0.12f),
                    unselectedIconColor = AfuColors.textMuted,
                    unselectedTextColor = AfuColors.textMuted
                )
            )
        }
    }
}
