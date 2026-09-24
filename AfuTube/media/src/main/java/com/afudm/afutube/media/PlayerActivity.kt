package com.afudm.afutube.media

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.ActivityInfo
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Forward10
import androidx.compose.material.icons.filled.Fullscreen
import androidx.compose.material.icons.filled.FullscreenExit
import androidx.compose.material.icons.filled.Headphones
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Replay10
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import com.afudm.afutube.core.theme.AfuColors
import androidx.compose.ui.graphics.toArgb
import com.google.common.util.concurrent.ListenableFuture
import java.io.File
import java.util.concurrent.Executor
import kotlinx.coroutines.delay

class PlayerActivity : ComponentActivity() {
    private var controller: androidx.media3.session.MediaController? = null
    private var future: ListenableFuture<androidx.media3.session.MediaController>? = null
    private var playerView: PlayerView? = null
    private var fullscreen by mutableStateOf(false)
    private var audioOnly by mutableStateOf(false)
    private var sourceAudioOnly by mutableStateOf(false)
    private var playbackError by mutableStateOf<String?>(null)
    private lateinit var path: String
    private lateinit var title: String
    private var explicitPath = false
    private var visible = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        fullscreen = savedInstanceState?.getBoolean(STATE_FULLSCREEN) ?: false
        window.statusBarColor = AfuColors.bg.toArgb()
        window.navigationBarColor = AfuColors.bg.toArgb()
        path = intent.getStringExtra(EXTRA_PATH).orEmpty()
        explicitPath = path.isNotBlank()
        title = intent.getStringExtra(EXTRA_TITLE)?.takeIf(String::isNotBlank) ?: File(path).nameWithoutExtension
        val token = androidx.media3.session.SessionToken(this, ComponentName(this, PlaybackService::class.java))
        future = androidx.media3.session.MediaController.Builder(this, token).buildAsync().also { f ->
            f.addListener({
                runCatching {
                    controller = f.get()
                    val player = controller ?: return@runCatching
                    val requestedPath = path
                    if (!explicitPath) {
                        val item = player.currentMediaItem
                        path = item?.mediaId?.takeIf { File(it).isFile } ?: item?.localConfiguration?.uri?.path.orEmpty()
                        title = item?.mediaMetadata?.title?.toString()?.takeIf(String::isNotBlank) ?: File(path).nameWithoutExtension
                    }
                    if (path.isBlank() || !File(path).isFile) {
                        showMissingFile()
                        return@runCatching
                    }
                    sourceAudioOnly = MediaFileTypeDetector.fromPath(path, this) == MediaFileType.AUDIO
                    audioOnly = when {
                        savedInstanceState?.containsKey(STATE_LISTEN_MODE) == true -> savedInstanceState.getBoolean(STATE_LISTEN_MODE)
                        intent.getBooleanExtra(EXTRA_LISTEN, false) -> true
                        !explicitPath -> getSharedPreferences(PREFERENCES, MODE_PRIVATE).getBoolean(PREF_LISTEN_MODE, false)
                        else -> sourceAudioOnly
                    }
                    player.addListener(object : Player.Listener {
                        override fun onPlayerError(error: PlaybackException) {
                            playbackError = "Oynatılamadı: ${error.message?.lineSequence()?.firstOrNull()?.take(120) ?: "Medya dosyası açılamadı"}"
                        }
                    })
                    setContent { PlayerScreen() }
                    if (explicitPath && player.currentMediaItem?.mediaId != requestedPath) {
                        player.setMediaItem(MediaItem.Builder().setMediaId(requestedPath).setUri(requestedPath).setMediaMetadata(MediaMetadata.Builder().setTitle(title).build()).build())
                        player.prepare()
                        player.play()
                    } else if (explicitPath && (player.playbackState == Player.STATE_ENDED || player.playbackState == Player.STATE_IDLE)) {
                        // Aynı dosya listeden yeniden açıldı ama çalma bitmiş/durmuş: baştan başlat.
                        if (player.playbackState == Player.STATE_IDLE) player.prepare()
                        player.seekTo(0)
                        player.play()
                    }
                    // Kullanıcı bağlantı kurulmadan ekrandan çıktıysa: İzle modunda arka planda çalma.
                    if (!visible && !audioOnly) player.pause()
                }.onFailure { Log.e("AfuTubePlayer", "Oynatıcı bağlantısı başarısız", it) }
            }, Executor { it.run() })
        }
    }

    private fun showMissingFile() {
        setContent {
            MaterialTheme {
                Box(Modifier.fillMaxSize().background(AfuColors.bg).padding(24.dp), contentAlignment = Alignment.Center) {
                    Text("Dosya bulunamadı", color = AfuColors.text, fontSize = 20.sp)
                }
            }
        }
    }

    @Composable
    private fun PlayerScreen() {
        val player = controller
        var position by remember { mutableLongStateOf(0L) }
        var duration by remember { mutableLongStateOf(0L) }
        var playing by remember { mutableStateOf(player?.isPlaying == true) }
        var dragging by remember { mutableStateOf(false) }
        var sliderPosition by remember { mutableFloatStateOf(0f) }
        SideEffect {
            WindowCompat.setDecorFitsSystemWindows(window, !fullscreen)
            val bars = WindowInsetsControllerCompat(window, window.decorView)
            if (fullscreen) bars.hide(WindowInsetsCompat.Type.systemBars())
            else bars.show(WindowInsetsCompat.Type.systemBars())
            playerView?.player = player
        }
        DisposableEffect(player) {
            onDispose { playerView?.player = null }
        }
        LaunchedEffect(player) {
            while (true) {
                position = player?.currentPosition?.coerceAtLeast(0L) ?: 0L
                duration = player?.duration?.takeIf { it > 0L } ?: 0L
                playing = player?.isPlaying == true
                if (!dragging) sliderPosition = if (duration > 0L) position.toFloat() / duration else 0f
                delay(500)
            }
        }
        BackHandler(enabled = fullscreen) { applyFullscreen(false) }

        MaterialTheme(colorScheme = darkColorScheme(background = AfuColors.bg, surface = AfuColors.surface, primary = AfuColors.accent, onBackground = AfuColors.text, onSurface = AfuColors.text)) {
            Column(Modifier.fillMaxSize().background(AfuColors.bg).systemBarsPadding()) {
                Row(Modifier.fillMaxWidth().heightIn(min = 60.dp).padding(horizontal = 8.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = { if (fullscreen) applyFullscreen(false) else finish() }) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Geri", tint = AfuColors.text)
                    }
                    Text(title, color = AfuColors.text, fontSize = 18.sp, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f).padding(end = 12.dp))
                }
                playbackError?.let { error ->
                    Text(error, color = AfuColors.error, fontSize = 12.sp, maxLines = 2, overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp).clip(RoundedCornerShape(10.dp)).background(AfuColors.error.copy(alpha = 0.12f)).padding(10.dp))
                }
                if (!fullscreen) {
                    Row(Modifier.align(Alignment.CenterHorizontally).padding(vertical = 8.dp).clip(RoundedCornerShape(16.dp)).background(AfuColors.surface).padding(4.dp), verticalAlignment = Alignment.CenterVertically) {
                        ModeButton("İzle", Icons.Default.Movie, selected = !audioOnly, enabled = !sourceAudioOnly) { setMode(false) }
                        ModeButton("Dinle", Icons.Default.Headphones, selected = audioOnly, enabled = true) { setMode(true) }
                    }
                }
                if (audioOnly) {
                    Column(Modifier.weight(1f).fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                        Box(Modifier.widthIn(max = 260.dp).fillMaxWidth().aspectRatio(1f).clip(RoundedCornerShape(24.dp)).background(Brush.linearGradient(listOf(AfuColors.accent, AfuColors.accentAlt))), contentAlignment = Alignment.Center) {
                            Icon(Icons.Default.Headphones, null, tint = Color.White, modifier = Modifier.size(104.dp))
                        }
                        Spacer(Modifier.height(24.dp))
                        Text(title, color = AfuColors.text, fontSize = 22.sp, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp), textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                        Spacer(Modifier.height(8.dp))
                        Text("Arka planda çalmaya devam eder", color = AfuColors.textMuted, fontSize = 14.sp)
                    }
                } else {
                    Box(Modifier.weight(1f).fillMaxWidth().padding(horizontal = if (fullscreen) 0.dp else 16.dp, vertical = if (fullscreen) 0.dp else 12.dp), contentAlignment = Alignment.Center) {
                        AndroidView(
                            factory = { ctx -> PlayerView(ctx).apply { useController = false; resizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT; this.player = this@PlayerActivity.controller; this@PlayerActivity.playerView = this } },
                            update = { it.player = player },
                            modifier = Modifier.fillMaxWidth().then(if (fullscreen) Modifier.fillMaxHeight() else Modifier.aspectRatio(16f / 9f).clip(RoundedCornerShape(16.dp))).background(Color.Black)
                        )
                        IconButton(onClick = { applyFullscreen(!fullscreen) }, modifier = Modifier.align(Alignment.BottomEnd).padding(8.dp).size(44.dp).clip(RoundedCornerShape(14.dp)).background(AfuColors.surface.copy(alpha = 0.9f)).semantics { contentDescription = "Tam ekran" }) {
                            Icon(if (fullscreen) Icons.Default.FullscreenExit else Icons.Default.Fullscreen, contentDescription = null, tint = AfuColors.text)
                        }
                    }
                }
                Column(Modifier.fillMaxWidth().background(AfuColors.surface.copy(alpha = 0.45f)).padding(horizontal = 20.dp, vertical = 12.dp)) {
                    Slider(value = if (dragging) sliderPosition else sliderPosition, onValueChange = { dragging = true; sliderPosition = it }, onValueChangeFinished = { player?.seekTo((sliderPosition * duration).toLong()); position = (sliderPosition * duration).toLong(); dragging = false }, valueRange = 0f..1f, enabled = duration > 0, colors = SliderDefaults.colors(thumbColor = AfuColors.accent, activeTrackColor = AfuColors.accent, inactiveTrackColor = AfuColors.textMuted.copy(alpha = 0.35f)), modifier = Modifier.fillMaxWidth().height(32.dp))
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(formatTime(position), color = AfuColors.textMuted, fontSize = 12.sp)
                        Text(formatTime(duration), color = AfuColors.textMuted, fontSize = 12.sp)
                    }
                    Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                        IconButton(onClick = { player?.seekTo((player.currentPosition - 10_000L).coerceAtLeast(0L)) }, modifier = Modifier.size(52.dp)) {
                            Icon(Icons.Default.Replay10, contentDescription = "10 saniye geri", tint = AfuColors.text, modifier = Modifier.size(30.dp))
                        }
                        Spacer(Modifier.width(24.dp))
                        FilledIconButton(onClick = { if (player?.isPlaying == true) player.pause() else player?.play() }, modifier = Modifier.size(64.dp), shape = RoundedCornerShape(50), colors = IconButtonDefaults.filledIconButtonColors(containerColor = AfuColors.accent, contentColor = Color.White)) {
                            Icon(if (playing) Icons.Default.Pause else Icons.Default.PlayArrow, contentDescription = if (playing) "Duraklat" else "Oynat", modifier = Modifier.size(38.dp))
                        }
                        Spacer(Modifier.width(24.dp))
                        IconButton(onClick = { player?.seekTo((player.currentPosition + 10_000L).coerceAtMost(duration)) }, modifier = Modifier.size(52.dp)) {
                            Icon(Icons.Default.Forward10, contentDescription = "10 saniye ileri", tint = AfuColors.text, modifier = Modifier.size(30.dp))
                        }
                    }
                }
            }
        }
    }

    @Composable
    private fun ModeButton(label: String, icon: androidx.compose.ui.graphics.vector.ImageVector, selected: Boolean, enabled: Boolean, onClick: () -> Unit) {
        val shape = RoundedCornerShape(12.dp)
        Surface(onClick = onClick, enabled = enabled, shape = shape, color = if (selected) AfuColors.accent else AfuColors.surface, modifier = Modifier.height(44.dp).semantics { contentDescription = label }) {
            Row(Modifier.padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                Icon(icon, null, tint = if (enabled) AfuColors.text else AfuColors.textMuted.copy(alpha = 0.45f), modifier = Modifier.size(18.dp))
                Text(label, color = if (enabled) AfuColors.text else AfuColors.textMuted.copy(alpha = 0.45f), fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
            }
        }
    }

    private fun setMode(listen: Boolean) {
        if (!listen && sourceAudioOnly) return
        audioOnly = listen
        getSharedPreferences(PREFERENCES, MODE_PRIVATE).edit().putBoolean(PREF_LISTEN_MODE, listen).apply()
        if (listen && controller?.playbackState == Player.STATE_ENDED) { controller?.seekTo(0); controller?.play() }
        requestedOrientation = if (listen) ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED else ActivityInfo.SCREEN_ORIENTATION_SENSOR
    }

    private fun applyFullscreen(enabled: Boolean) {
        fullscreen = enabled
        requestedOrientation = if (enabled) ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE else ActivityInfo.SCREEN_ORIENTATION_SENSOR
        val bars = WindowInsetsControllerCompat(window, window.decorView)
        if (enabled) bars.hide(WindowInsetsCompat.Type.systemBars()) else bars.show(WindowInsetsCompat.Type.systemBars())
        WindowCompat.setDecorFitsSystemWindows(window, !enabled)
    }

    override fun onStart() { super.onStart(); visible = true }
    override fun onStop() { visible = false; if (!isChangingConfigurations && !audioOnly) controller?.pause(); super.onStop() }
    override fun onSaveInstanceState(outState: Bundle) {
        outState.putBoolean(STATE_FULLSCREEN, fullscreen)
        outState.putBoolean(STATE_LISTEN_MODE, audioOnly)
        super.onSaveInstanceState(outState)
    }
    override fun onDestroy() { playerView?.player = null; future?.let { androidx.media3.session.MediaController.releaseFuture(it) }; controller = null; super.onDestroy() }

    companion object {
        const val EXTRA_PATH = "media_path"
        const val EXTRA_TITLE = "media_title"
        const val EXTRA_LISTEN = "start_listen"
        private const val PREFERENCES = "playback_preferences"
        private const val PREF_LISTEN_MODE = "listen_mode"
        private const val STATE_FULLSCREEN = "fullscreen"
        private const val STATE_LISTEN_MODE = "listen_mode_state"
        fun intent(context: Context, path: String, title: String) = Intent(context, PlayerActivity::class.java).putExtra(EXTRA_PATH, path).putExtra(EXTRA_TITLE, title)
    }
}

private fun formatTime(positionMs: Long): String {
    val totalSeconds = (positionMs.coerceAtLeast(0L) / 1000L)
    val seconds = totalSeconds % 60
    val minutes = (totalSeconds / 60) % 60
    val hours = totalSeconds / 3600
    return if (hours > 0) "%d:%02d:%02d".format(hours, minutes, seconds) else "%d:%02d".format(totalSeconds / 60, seconds)
}
