package com.afudm.afutube.media

import android.content.ContentUris
import android.content.Context
import android.content.IntentSender
import android.net.Uri
import android.media.MediaScannerConnection
import android.os.Build
import android.provider.MediaStore
import java.io.File

object MediaDelete {
    fun request(context: Context, file: File): IntentSender? {
        if (Build.VERSION.SDK_INT < 29) return null
        val uri = findUri(context, file) ?: return null
        return requestUri(context, uri)
    }
    fun requestUri(context: Context, uri: Uri): IntentSender? = when {
        Build.VERSION.SDK_INT >= 30 -> MediaStore.createDeleteRequest(context.contentResolver, listOf(uri)).intentSender
        Build.VERSION.SDK_INT == 29 -> try { context.contentResolver.delete(uri, null, null); null }
            catch (denied: android.app.RecoverableSecurityException) { denied.userAction.actionIntent.intentSender }
        else -> null
    }
    fun deleteLegacy(context: Context, file: File): Boolean {
        if (Build.VERSION.SDK_INT >= 29) return false
        val deleted = file.delete()
        if (deleted) MediaScannerConnection.scanFile(context, arrayOf(file.absolutePath), null, null)
        return deleted
    }
    private fun findUri(context: Context, file: File) = sequenceOf(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, MediaStore.Audio.Media.EXTERNAL_CONTENT_URI, MediaStore.Downloads.EXTERNAL_CONTENT_URI)
        .mapNotNull { collection ->
            val projection = arrayOf(MediaStore.MediaColumns._ID)
            context.contentResolver.query(collection, projection, "${MediaStore.MediaColumns.DATA}=?", arrayOf(file.absolutePath), null)?.use { c ->
                if (c.moveToFirst()) ContentUris.withAppendedId(collection, c.getLong(0)) else null
            }
        }.firstOrNull()
}
