package com.afudm.afutube.feature.downloads

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.provider.DocumentsContract

/**
 * Klasor acma icin saf yardimcilar Android bagimliligi olmadan test edilebilir.
 */
fun folderDocumentId(folderPath: String, storageRoot: String): String? {
    if (storageRoot.isBlank()) return null
    val root = storagePath(storageRoot)
    val folder = storagePath(folderPath)
    if (folder == root) return "$PRIMARY_VOLUME:"
    if (!folder.startsWith("$root/")) return null
    val relative = folder.removePrefix("$root/").trim('/')
    if (relative.isBlank()) return "$PRIMARY_VOLUME:"
    return "$PRIMARY_VOLUME:$relative"
}

/** Android 11+ dosya yoneticisinin gosteremedigi uygulama klasorlerini tanir. */
fun isHiddenAppFolder(folderDocumentId: String?): Boolean {
    if (folderDocumentId.isNullOrBlank()) return false
    val relative = folderDocumentId.substringAfter(':', "").trim('/')
    return relative == "Android/data" ||
        relative.startsWith("Android/data/") ||
        relative.startsWith("Android/obb/")
}

private fun storagePath(path: String): String =
    path.replace('\\', '/').trimEnd('/')

private const val PRIMARY_VOLUME = "primary"
private const val EXTERNAL_STORAGE_AUTHORITY = "com.android.externalstorage.documents"

/** Indirilen dosyanin bulundugu klasoru sistem dosya yoneticisinde acar. */
fun openDownloadFolder(context: Context, path: String) {
    val folder = java.io.File(path).parentFile ?: return
    val documentId = folderDocumentId(folder.absolutePath, storageRoot())
    if (documentId == null) {
        openStorageRoot(context)
        return
    }
    val opened = startFolderIntent(context, documentUri(documentId)) ||
        startFolderIntent(context, storageRootUri())
    if (!opened) {
        if (isHiddenAppFolder(documentId)) {
            toast(context, "Bu klasor telefonda gorunmuyor. Dosyayi paylasmak icin Paylas'a dokun.")
        } else {
            toast(context, "Klasor acilamadi.")
        }
    }
}

@Suppress("DEPRECATION")
private fun storageRoot(): String = Environment.getExternalStorageDirectory()?.absolutePath.orEmpty()

private fun documentUri(documentId: String): Uri = DocumentsContract.buildDocumentUri(
    EXTERNAL_STORAGE_AUTHORITY, documentId
)

private fun storageRootUri(): Uri = documentUri("$PRIMARY_VOLUME:")

private fun openStorageRoot(context: Context) {
    if (!startFolderIntent(context, storageRootUri())) toast(context, "Klasor acilamadi.")
}

private fun startFolderIntent(context: Context, uri: Uri): Boolean {
    val intent = Intent(Intent.ACTION_VIEW).apply {
        setDataAndType(uri, DocumentsContract.Document.MIME_TYPE_DIR)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    return runCatching { context.startActivity(intent) }.isSuccess
}

private fun toast(context: Context, message: String) =
    android.widget.Toast.makeText(context, message, android.widget.Toast.LENGTH_LONG).show()
