package com.afudm.afutube.media

import android.app.PendingIntent
import android.content.Intent
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.Player
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService

class PlaybackService : MediaSessionService() {
    private var player: ExoPlayer? = null
    private var session: MediaSession? = null

    override fun onCreate() {
        super.onCreate()
        val exo = ExoPlayer.Builder(this).build().apply {
            setWakeMode(C.WAKE_MODE_LOCAL)
            setAudioAttributes(AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MOVIE).build(), true)
            setHandleAudioBecomingNoisy(true)
            val preferences = getSharedPreferences(PlayerActivity.PREFERENCES, MODE_PRIVATE)
            repeatMode = preferences.getInt(PlayerActivity.PREF_REPEAT_MODE, Player.REPEAT_MODE_OFF)
                .takeIf { it in Player.REPEAT_MODE_OFF..Player.REPEAT_MODE_ALL } ?: Player.REPEAT_MODE_OFF
            addListener(object : Player.Listener {
                override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                    val contentMusic = mediaItem?.localConfiguration?.uri?.scheme == "content"
                    val activity = if (contentMusic) {
                        packageManager.getLaunchIntentForPackage(packageName)?.putExtra("open_music", true)
                    } else Intent(this@PlaybackService, PlayerActivity::class.java)
                    activity?.let {
                        session?.setSessionActivity(PendingIntent.getActivity(this@PlaybackService,
                            if (contentMusic) 2 else 1, it, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
                    }
                }
                override fun onRepeatModeChanged(repeatMode: Int) {
                    preferences.edit().putInt(PlayerActivity.PREF_REPEAT_MODE, repeatMode).apply()
                }
            })
        }
        player = exo
        session = MediaSession.Builder(this, exo)
            .setSessionActivity(PendingIntent.getActivity(this, 1, Intent(this, PlayerActivity::class.java), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
            .build()
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? = session

    override fun onTaskRemoved(rootIntent: Intent?) {
        if (player?.isPlaying != true) stopSelf()
    }

    override fun onDestroy() {
        session?.release()
        session = null
        player?.release()
        player = null
        super.onDestroy()
    }
}
