package com.afudm.afutube.core.share

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.webkit.MimeTypeMap
import android.widget.Toast
import androidx.core.content.FileProvider
import java.io.File

/** Common file and text sharing behavior for AfuTube. */
object ShareHelper {
    private const val WHATSAPP = "com.whatsapp"
    private const val WHATSAPP_BUSINESS = "com.whatsapp.w4b"

    /** Kept Android-free so target selection order can be verified in a JVM test. */
    internal fun preferredPackage(isInstalled: (String) -> Boolean): String? =
        listOf(WHATSAPP, WHATSAPP_BUSINESS).firstOrNull(isInstalled)

    fun shareText(context: Context, text: String) {
        val intent = Intent(Intent.ACTION_SEND)
            .setType("text/plain")
            .putExtra(Intent.EXTRA_TEXT, text)
        launchShare(context, intent, "AfuTube'u paylaş")
    }

    fun shareFile(context: Context, file: File, title: String) =
        shareFile(context, createShareUri(context, file), title)

    fun shareFile(context: Context, uri: Uri, title: String, text: String? = null) {
        val mimeType = shareMimeType(context, uri)
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = mimeType
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            // setClipData Unit dondurur; zincirin sonunda kalirsa intent Unit olur.
            clipData = android.content.ClipData.newUri(context.contentResolver, title, uri)
        }
        if (!text.isNullOrBlank()) intent.putExtra(Intent.EXTRA_TEXT, text)
        launchShare(context, intent, title)
    }

    fun createShareUri(context: Context, file: File): Uri =
        FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)

    fun shareMimeType(context: Context, uri: Uri): String {
        context.contentResolver.getType(uri)?.let { return it }
        val extension = when (uri.scheme) {
            "file" -> MimeTypeMap.getFileExtensionFromUrl(uri.toString())
            else -> uri.lastPathSegment?.substringAfterLast('.', "")
        }
        return MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension?.lowercase().orEmpty())
            ?: "application/octet-stream"
    }

    private fun launchShare(context: Context, intent: Intent, chooserTitle: String) {
        val target = preferredPackage { packageName ->
            try {
                @Suppress("DEPRECATION")
                context.packageManager.getPackageInfo(packageName, 0)
                true
            } catch (_: PackageManager.NameNotFoundException) {
                false
            }
        }
        try {
            if (target != null) {
                // Starting directly avoids a second resolver appearing after Back on some Android versions.
                context.startActivity(intent.setPackage(target))
            } else {
                context.startActivity(Intent.createChooser(intent, chooserTitle))
            }
        } catch (_: Exception) {
            if (target != null) {
                try {
                    context.startActivity(Intent.createChooser(intent.setPackage(null), chooserTitle))
                    return
                } catch (_: Exception) {
                    // Show the same short message if Android has no compatible share target.
                }
            }
            Toast.makeText(context, "Paylaşılacak uygulama bulunamadı.", Toast.LENGTH_SHORT).show()
        }
    }
}
