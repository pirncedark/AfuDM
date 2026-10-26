package com.afudm.afutube.media

import android.content.ContentUris
import android.content.Context
import android.os.Build
import android.provider.MediaStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.Locale

data class MusicTrack(val uri: String, val title: String, val artist: String, val album: String = "", val folder: String = "", val durationMs: Long = 0, val albumId: Long = 0)

data class MusicGroup(val title: String, val tracks: List<MusicTrack>)
internal fun groupMusic(tracks: List<MusicTrack>): List<MusicGroup> = tracks
    .groupBy { it.folder.ifBlank { "Bilinmeyen klasör" } }
    .map { MusicGroup(it.key, it.value) }
    .sortedBy { it.title.lowercase(Locale.ROOT) }

internal fun seekPosition(positionMs: Long, durationMs: Long, deltaMs: Long): Long =
    (positionMs + deltaMs).coerceIn(0L, durationMs.coerceAtLeast(0L))

internal fun musicPermission(sdk: Int): String = if (sdk >= 33)
    "android.permission.READ_MEDIA_AUDIO" else "android.permission.READ_EXTERNAL_STORAGE"

internal fun isMusicEntry(isMusic: Boolean, path: String): Boolean {
    val normalized = "/${path.trim('/').lowercase(Locale.ROOT)}/"
    return isMusic || normalized.contains("/music/") || normalized.contains("/download/afutube/")
}

internal fun prepareMusicList(tracks: List<MusicTrack>): List<MusicTrack> = tracks
    .distinctBy { it.uri }.sortedWith(compareBy({ it.title.lowercase(Locale.ROOT) }, { it.uri }))

suspend fun loadMusic(context: Context): List<MusicTrack> = withContext(Dispatchers.IO) {
    val collection = MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
    val pathColumn = if (Build.VERSION.SDK_INT >= 29) MediaStore.Audio.Media.RELATIVE_PATH
        else MediaStore.Audio.Media.DATA
    val projection = arrayOf(MediaStore.Audio.Media._ID, MediaStore.Audio.Media.TITLE,
        MediaStore.Audio.Media.DISPLAY_NAME, MediaStore.Audio.Media.ARTIST,
        MediaStore.Audio.Media.IS_MUSIC, pathColumn, MediaStore.Audio.Media.ALBUM, MediaStore.Audio.Media.DURATION,
        MediaStore.Audio.Media.ALBUM_ID)
    val tracks = mutableListOf<MusicTrack>()
    val selection = if (Build.VERSION.SDK_INT >= 29) "${MediaStore.Audio.Media.IS_PENDING}=0" else null
    val cursor = context.contentResolver.query(collection, projection, selection, null, null)
        ?: error("Music query returned no cursor")
    cursor.use {
        while (it.moveToNext()) {
            if (!isMusicEntry(it.getInt(4) != 0, it.getString(5).orEmpty())) continue
            tracks += MusicTrack(ContentUris.withAppendedId(collection, it.getLong(0)).toString(),
                it.getString(1)?.takeIf(String::isNotBlank) ?: it.getString(2).orEmpty(),
                it.getString(3)?.takeUnless { artist -> artist == "<unknown>" }.orEmpty(),
                it.getString(6)?.takeUnless { album -> album == "<unknown>" }.orEmpty(),
                it.getString(5).orEmpty().trimEnd('/').substringAfterLast('/').takeIf { folder -> folder.isNotBlank() } ?: "Müzik",
                it.getLong(7), it.getLong(8))
        }
    }
    prepareMusicList(tracks)
}
