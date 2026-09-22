package com.afudm.afutube

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.*
import androidx.navigation.NavType
import androidx.navigation.compose.*
import androidx.navigation.navArgument
import com.afudm.afutube.core.extractor.MediaInfo
import com.afudm.afutube.feature.home.HomeScreen
import com.afudm.afutube.feature.formats.FormatPickerScreen
import com.yausername.aria2c.Aria2c
import com.yausername.ffmpeg.FFmpeg
import com.yausername.youtubedl_android.YoutubeDL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private var sharedUrl: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Share Intent'ten URL al
        sharedUrl = extractUrlFromIntent(intent)

        // yt-dlp + FFmpeg + aria2c başlatma (arka plan thread'de)
        lifecycleScope.launch(Dispatchers.IO) {
            runCatching {
                YoutubeDL.getInstance().init(application)
                FFmpeg.getInstance().init(application)
                Aria2c.getInstance().init(application)
            }
        }

        setContent {
            AfuTubeApp(sharedUrl = sharedUrl)
        }
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        // Uygulama açıkken yeni Share gelirse
        sharedUrl = intent?.let { extractUrlFromIntent(it) }
    }

    private fun extractUrlFromIntent(intent: Intent?): String? {
        if (intent?.action != Intent.ACTION_SEND) return null
        if (intent.type != "text/plain") return null
        return intent.getStringExtra(Intent.EXTRA_TEXT)
            ?.trim()
            ?.let { if (it.startsWith("http") ) it else null }
    }
}

// ── Navigation ────────────────────────────────────────────────────────────────

@Composable
fun AfuTubeApp(sharedUrl: String? = null) {
    val navController = rememberNavController()
    var pendingMediaInfo by remember { mutableStateOf<MediaInfo?>(null) }

    NavHost(navController = navController, startDestination = "home") {

        composable("home") {
            HomeScreen(
                sharedUrl = sharedUrl,
                onNavigateToFormats = { info ->
                    pendingMediaInfo = info
                    navController.navigate("formats")
                }
            )
        }

        composable("formats") {
            val info = pendingMediaInfo
            if (info != null) {
                FormatPickerScreen(
                    mediaInfo  = info,
                    onBack     = { navController.popBackStack() },
                    onDownload = { navController.popBackStack() }
                )
            }
        }
    }
}
