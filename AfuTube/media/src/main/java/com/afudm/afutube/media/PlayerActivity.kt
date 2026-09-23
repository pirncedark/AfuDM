package com.afudm.afutube.media

import android.app.Activity
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.ActivityInfo
import android.os.Bundle
import android.util.Log
import android.view.View
import android.view.WindowManager
import android.content.res.ColorStateList
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.common.PlaybackException
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import androidx.media3.ui.PlayerControlView
import androidx.media3.ui.PlayerView
import com.afudm.afutube.core.theme.AfuColors
import androidx.compose.ui.graphics.toArgb
import java.io.File
import java.util.concurrent.Executor

class PlayerActivity : Activity() {
    private var controller: MediaController? = null
    private var future: com.google.common.util.concurrent.ListenableFuture<MediaController>? = null
    private var playerView: PlayerView? = null
    private var audioControls: PlayerControlView? = null
    private var videoButton: Button? = null
    private var audioButton: Button? = null
    private var fullscreenButton: Button? = null
    private var errorText: TextView? = null
    private var fullscreen = false
    private var audioOnly = false
    private var sourceAudioOnly = false
    private lateinit var path: String
    private lateinit var title: String
    private var explicitPath = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        path = intent.getStringExtra(EXTRA_PATH).orEmpty()
        explicitPath = path.isNotBlank()
        title = intent.getStringExtra(EXTRA_TITLE)?.takeIf(String::isNotBlank) ?: File(path).nameWithoutExtension
        val token = SessionToken(this, ComponentName(this, PlaybackService::class.java))
        future = MediaController.Builder(this, token).buildAsync().also { f ->
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
                        intent.getBooleanExtra(EXTRA_LISTEN, false) -> true
                        !explicitPath -> getSharedPreferences(PREFERENCES, MODE_PRIVATE).getBoolean(PREF_LISTEN_MODE, false)
                        else -> sourceAudioOnly
                    }
                    player.addListener(object : Player.Listener {
                        override fun onPlayerError(error: PlaybackException) {
                            errorText?.text = "Oynat\u0131lamad\u0131: ${error.message?.lineSequence()?.firstOrNull()?.take(120) ?: "Medya dosyas\u0131 a\u00e7\u0131lamad\u0131"}"
                            errorText?.visibility = View.VISIBLE
                        }
                    })
                    buildUi()
                    playerView?.player = player
                    audioControls?.player = player
                    if (explicitPath && player.currentMediaItem?.mediaId != requestedPath) {
                        player.setMediaItem(MediaItem.Builder().setMediaId(requestedPath).setUri(requestedPath).setMediaMetadata(MediaMetadata.Builder().setTitle(title).build()).build())
                        player.prepare()
                        player.play()
                    } else if (explicitPath && (player.playbackState == Player.STATE_ENDED || player.playbackState == Player.STATE_IDLE)) {
                        // Ayni dosya listeden yeniden acildi ama calma bitmis/durmus: bastan baslat.
                        if (player.playbackState == Player.STATE_IDLE) player.prepare()
                        player.seekTo(0)
                        player.play()
                    }
                }.onFailure { Log.e("AfuTubePlayer", "Oynatici baglantisi basarisiz", it) }
            }, Executor { it.run() })
        }
    }

    private fun showMissingFile() {
        setContentView(TextView(this).apply {
            text = "Dosya bulunamad\u0131"
            setTextColor(AfuColors.text.toArgb()); textSize = 20f; setPadding(32, 48, 32, 32)
            setBackgroundColor(AfuColors.bg.toArgb())
        })
    }

    private fun buildUi() {
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(16, 20, 16, 16); setBackgroundColor(AfuColors.bg.toArgb()) }
        setContentView(root)
        val header = TextView(this).apply { text = title; textSize = 24f; setTextColor(AfuColors.text.toArgb()); maxLines = 2 }
        root.addView(header, LinearLayout.LayoutParams(-1, -2))
        errorText = TextView(this).apply { setTextColor(AfuColors.text.toArgb()); visibility = View.GONE }
        root.addView(errorText, LinearLayout.LayoutParams(-1, -2))
        val tabs = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        videoButton = Button(this).apply { text = "İzle"; contentDescription = "İzle"; setOnClickListener { showMode(false) } }
        audioButton = Button(this).apply { text = "Dinle"; contentDescription = "Dinle"; setOnClickListener { showMode(true) } }
        fullscreenButton = Button(this).apply {
            text = "Tam ekran"
            setTextColor(AfuColors.text.toArgb())
            backgroundTintList = ColorStateList.valueOf(AfuColors.surface.toArgb())
            setOnClickListener {
                fullscreen = !fullscreen
                requestedOrientation = if (fullscreen) ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE else ActivityInfo.SCREEN_ORIENTATION_SENSOR
                window.setFlags(if (fullscreen) WindowManager.LayoutParams.FLAG_FULLSCREEN else 0, WindowManager.LayoutParams.FLAG_FULLSCREEN)
            }
        }
        listOf(videoButton, audioButton).forEach { button ->
            button?.setTextColor(AfuColors.text.toArgb())
            button?.backgroundTintList = ColorStateList.valueOf(AfuColors.surface.toArgb())
        }
        tabs.addView(videoButton)
        tabs.addView(audioButton)
        tabs.addView(fullscreenButton)
        root.addView(tabs)
        playerView = PlayerView(this).apply { useController = false }
        root.addView(playerView, LinearLayout.LayoutParams(-1, 0, 1f))
        val controls = PlayerControlView(this)
        controls.showTimeoutMs = 0
        audioControls = controls
        root.addView(controls, LinearLayout.LayoutParams(-1, -2))
        showMode(audioOnly)
    }

    private fun showMode(listen: Boolean) {
        audioOnly = listen
        getSharedPreferences(PREFERENCES, MODE_PRIVATE).edit().putBoolean(PREF_LISTEN_MODE, listen).apply()
        if (listen && controller?.playbackState == Player.STATE_ENDED) {
            controller?.seekTo(0)
            controller?.play()
        }
        playerView?.visibility = if (listen) View.GONE else View.VISIBLE
        audioControls?.visibility = View.VISIBLE
        requestedOrientation = if (listen) ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED else ActivityInfo.SCREEN_ORIENTATION_SENSOR
        videoButton?.isEnabled = !sourceAudioOnly
        audioButton?.isEnabled = true
        fullscreenButton?.visibility = if (listen) View.GONE else View.VISIBLE
    }

    override fun onStop() {
        if (!isChangingConfigurations && !audioOnly) controller?.pause()
        super.onStop()
    }

    override fun onDestroy() {
        playerView?.player = null
        audioControls?.player = null
        future?.let { MediaController.releaseFuture(it) }
        controller = null
        super.onDestroy()
    }

    companion object {
        const val EXTRA_PATH = "media_path"
        const val EXTRA_TITLE = "media_title"
        const val EXTRA_LISTEN = "start_listen"
        private const val PREFERENCES = "playback_preferences"
        private const val PREF_LISTEN_MODE = "listen_mode"
        fun intent(context: Context, path: String, title: String) = Intent(context, PlayerActivity::class.java).putExtra(EXTRA_PATH, path).putExtra(EXTRA_TITLE, title)
    }
}
