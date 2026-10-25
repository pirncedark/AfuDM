package com.afudm.afutube.media

import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.database.ContentObserver
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.provider.Settings
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.afudm.afutube.core.theme.AfuColors
import kotlinx.coroutines.CancellationException

/** The service owns playback; leaving this screen only disconnects its controller. */
@Composable
fun MusicScreen() {
    val context = LocalContext.current
    val permission = remember { musicPermission(Build.VERSION.SDK_INT) }
    val preferences = remember { context.getSharedPreferences("afutube_music", 0) }
    var granted by remember { mutableStateOf(context.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED) }
    var refresh by remember { mutableIntStateOf(0) }
    var tracks by remember { mutableStateOf(emptyList<MusicTrack>()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var guidance by remember { mutableStateOf(!preferences.getBoolean("guidance_seen", false)) }
    var controller by remember { mutableStateOf<MediaController?>(null) }
    var connectionAttempt by remember { mutableIntStateOf(0) }
    var playing by remember { mutableStateOf(false) }
    var currentTitle by remember { mutableStateOf("") }
    var currentId by remember { mutableStateOf("") }
    var previous by remember { mutableStateOf(false) }
    var next by remember { mutableStateOf(false) }
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        granted = it
        if (it) refresh++
    }

    LaunchedEffect(Unit) {
        preferences.edit().putBoolean("guidance_seen", true).apply()
        if (!granted && !preferences.getBoolean("permission_asked", false)) {
            preferences.edit().putBoolean("permission_asked", true).apply()
            permissionLauncher.launch(permission)
        }
    }
    DisposableEffect(context) {
        val lifecycle = (context as? ComponentActivity)?.lifecycle
        val listener = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                granted = context.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED
                refresh++
            }
        }
        lifecycle?.addObserver(listener)
        val observer = object : ContentObserver(Handler(Looper.getMainLooper())) {
            override fun onChange(selfChange: Boolean) { refresh++ }
        }
        context.contentResolver.registerContentObserver(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI, true, observer)
        onDispose {
            lifecycle?.removeObserver(listener)
            context.contentResolver.unregisterContentObserver(observer)
        }
    }
    LaunchedEffect(granted, refresh) {
        if (!granted) { tracks = emptyList(); return@LaunchedEffect }
        loading = true
        error = null
        try {
            tracks = loadMusic(context)
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (failure: Exception) {
            Log.e("AfuTubeMusic", "Cannot load music", failure)
            error = "Müzikler okunamadı, izni kontrol edip yeniden dene."
        } finally { loading = false }
    }
    DisposableEffect(context, connectionAttempt) {
        var disposed = false
        val future = MediaController.Builder(context,
            SessionToken(context, ComponentName(context, PlaybackService::class.java))).buildAsync()
        fun update(player: Player) {
            playing = player.isPlaying
            currentTitle = player.currentMediaItem?.mediaMetadata?.title?.toString().orEmpty()
            currentId = player.currentMediaItem?.mediaId.orEmpty()
            previous = player.hasPreviousMediaItem()
            next = player.hasNextMediaItem()
        }
        val listener = object : Player.Listener {
            override fun onEvents(player: Player, events: Player.Events) {
                update(player)
            }
            override fun onPlayerError(failure: PlaybackException) {
                Log.e("AfuTubeMusic", "Playback failed", failure)
                error = "Bu müzik çalınamadı, başka bir parça seç."
            }
        }
        future.addListener({
            if (!disposed) {
                try {
                    val player = future.get()
                    controller = player
                    player.addListener(listener)
                    update(player)
                } catch (failure: Exception) {
                    Log.e("AfuTubeMusic", "Controller connection failed", failure)
                    error = "Oynatıcı açılamadı, yeniden dene."
                }
            }
        }, ContextCompat.getMainExecutor(context))
        onDispose {
            disposed = true
            controller?.removeListener(listener)
            controller = null
            MediaController.releaseFuture(future)
        }
    }

    Column(Modifier.fillMaxSize().background(AfuColors.bg).padding(horizontal = 16.dp)) {
        Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("Müzik", style = MaterialTheme.typography.headlineMedium, color = AfuColors.text, modifier = Modifier.weight(1f))
            IconButton(onClick = { refresh++; if (controller == null) connectionAttempt++ }) {
                Icon(Icons.Default.Refresh, "Yenile", tint = AfuColors.accent)
            }
        }
        if (guidance) {
            Text("Telefonundaki müziklerden birini seç; ekran kapalıyken de çalmaya devam eder.", color = AfuColors.textMuted)
            TextButton(onClick = {
                guidance = false
                preferences.edit().putBoolean("guidance_seen", true).apply()
            }) { Text("Anladım") }
        }
        error?.let { Text(it, color = AfuColors.error, modifier = Modifier.padding(vertical = 8.dp)) }
        if (!granted) {
            Column(Modifier.weight(1f).fillMaxWidth(), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
                Text("Müziklerini görmek için erişime izin ver.", color = AfuColors.text)
                Button(onClick = {
                    val activity = context as? ComponentActivity
                    if (preferences.getBoolean("permission_asked", false) && activity != null &&
                        !activity.shouldShowRequestPermissionRationale(permission)) {
                        context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}")))
                    } else {
                        preferences.edit().putBoolean("permission_asked", true).apply()
                        permissionLauncher.launch(permission)
                    }
                }, modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) { Text("Müziklere erişim ver") }
            }
        } else if (loading) {
            Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = AfuColors.accent) }
        } else {
            if (tracks.isEmpty() && error == null) Text("Henüz müzik yok; telefonuna müzik eklediğinde burada görünür.", color = AfuColors.textMuted)
            LazyColumn(Modifier.weight(1f)) {
                items(tracks, key = { it.uri }) { track ->
                    ListItem(
                        headlineContent = { Text(track.title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                        supportingContent = { Text(track.artist, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                        leadingContent = { Icon(if (track.uri == currentId && playing) Icons.Default.VolumeUp else Icons.Default.MusicNote, null) },
                        colors = ListItemDefaults.colors(containerColor = if (track.uri == currentId) AfuColors.card else AfuColors.bg,
                            headlineColor = AfuColors.text, supportingColor = AfuColors.textMuted, leadingIconColor = AfuColors.accent),
                        modifier = Modifier.clickable(enabled = controller != null) {
                            val player = controller ?: return@clickable
                            error = null
                            if (player.currentMediaItem?.mediaId == track.uri) {
                                if (player.playbackState == Player.STATE_IDLE) player.prepare()
                                if (player.playbackState == Player.STATE_ENDED) player.seekTo(0L)
                                player.play()
                            } else {
                                player.setMediaItems(tracks.map {
                                    MediaItem.Builder().setMediaId(it.uri).setUri(it.uri)
                                        .setMediaMetadata(MediaMetadata.Builder().setTitle(it.title).setArtist(it.artist)
                                            .setIsPlayable(true).setMediaType(MediaMetadata.MEDIA_TYPE_MUSIC).build()).build()
                                }, tracks.indexOf(track), 0L)
                                player.prepare()
                                player.play()
                            }
                        }
                    )
                }
            }
        }
        if (currentTitle.isNotBlank()) {
            Text(currentTitle, color = AfuColors.text, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 12.dp))
            Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { controller?.seekToPreviousMediaItem() }, enabled = previous) { Icon(Icons.Default.SkipPrevious, "Önceki", tint = AfuColors.textMuted) }
                Button(onClick = {
                    controller?.let { player ->
                        if (player.isPlaying) player.pause() else {
                            if (player.playbackState == Player.STATE_IDLE) player.prepare()
                            if (player.playbackState == Player.STATE_ENDED) player.seekTo(0L)
                            player.play()
                        }
                    }
                }) { Icon(if (playing) Icons.Default.Pause else Icons.Default.PlayArrow, null); Text(if (playing) "Duraklat" else "Oynat") }
                IconButton(onClick = { controller?.seekToNextMediaItem() }, enabled = next) { Icon(Icons.Default.SkipNext, "Sonraki", tint = AfuColors.textMuted) }
            }
        }
    }
}
