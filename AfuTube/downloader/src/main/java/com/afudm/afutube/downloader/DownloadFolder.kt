package com.afudm.afutube.downloader

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.webkit.MimeTypeMap
import java.io.File

/**
 * Indirilen dosyalarin telefonda gorunur "afutube" klasorune yazilmasi.
 *
 * Android 10 ve sonrasinda uygulamalar genel klasorlere dogrudan dosya yazamaz.
 * Bu yuzden indirme once uygulama icindeki gecici klasore yapilir, bittikten
 * sonra [publish] dosyayi "Download/afutube" klasorune tasir.
 * Klasor yazilabilir degilse dosya gecici klasorde kalir; indirme yine basarilidir.
 */
object DownloadFolder {

    const val NAME = "afutube"

    /** Kullanicinin gorecegi klasorun MediaStore'a verilecek goreli yolu. */
    const val RELATIVE_PATH = "Download/$NAME"

    /** Indirmenin gecici olarak yazildigi klasor (uygulama ici, temizlenebilir). */
    fun stagingDir(context: Context): File =
        File(context.getExternalFilesDir(null) ?: context.filesDir, "downloads").apply { mkdirs() }

    /** Klasorun dosya sistemindeki yolu (Android 10 ve altinda dogrudan yazilabilir). */
    fun visibleDir(): File =
        File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), NAME)

    /**
     * Indirilen dosyayi gorunur afutube klasorune tasir.
     * @return Gorunur klasordeki dosyanin tam yolu. Tasima basarisizsa kaynak dosyanin yolu.
     */
    fun publish(context: Context, source: File): String {
        if (!source.isFile) return source.absolutePath
        if (isInsideVisibleDir(source)) return source.absolutePath

        val ad = benzersizAd(visibleDir().list()?.toList().orEmpty(), source.name)
        val target = File(visibleDir(), ad)
        if (copyTo(source, target)) {
            source.delete()
            return target.absolutePath
        }
        if (insertViaMediaStore(context, source, ad)) {
            // MediaStore dosyayi bazen yeniden adlandirir; gercek yol bulunamazsa gecici dosya kalir.
            val gorunurYol = mediaStorePath(context, ad) ?: target.takeIf { it.isFile }?.absolutePath
            if (gorunurYol != null) {
                source.delete()
                return gorunurYol
            }
        }
        return source.absolutePath
    }

    @Suppress("DEPRECATION")
    private fun mediaStorePath(context: Context, ad: String): String? = runCatching {
        context.contentResolver.query(
            MediaStore.Files.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY),
            arrayOf(MediaStore.MediaColumns.DATA),
            "${MediaStore.MediaColumns.RELATIVE_PATH}=? AND ${MediaStore.MediaColumns.DISPLAY_NAME}=?",
            arrayOf(RELATIVE_PATH, ad),
            null
        )?.use { c -> if (c.moveToFirst()) c.getString(0) else null }
    }.getOrNull()?.takeIf { File(it).isFile }

    private fun isInsideVisibleDir(file: File): Boolean {
        val root = visibleDir().absolutePath.trimEnd('/')
        return file.absolutePath.startsWith("$root/")
    }

    private fun copyTo(source: File, target: File): Boolean = runCatching {
        if (!target.parentFile?.isDirectory!!) target.parentFile?.mkdirs()
        if (target.exists()) target.delete()
        source.copyTo(target, overwrite = true)
        target.isFile && target.length() == source.length()
    }.getOrDefault(false)

    /** Android 10+ icin MediaStore uzerinden gorunur klasore yazma. */
    private fun insertViaMediaStore(context: Context, source: File, ad: String): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return false
        val resolver = context.contentResolver
        val mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(source.extension.lowercase())
        val collection = if (mime != null && mime != "application/octet-stream") {
            MediaStore.Downloads.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        } else {
            MediaStore.Files.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        }
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, ad)
            put(MediaStore.MediaColumns.MIME_TYPE, mime ?: "application/octet-stream")
            put(MediaStore.MediaColumns.RELATIVE_PATH, RELATIVE_PATH)
            put(MediaStore.MediaColumns.IS_PENDING, 1)
        }
        val uri: Uri = runCatching {
            resolver.insert(collection, values) ?: return false
        }.getOrNull() ?: return false

        val written = runCatching {
            resolver.openOutputStream(uri)?.use { output ->
                source.inputStream().use { input -> input.copyTo(output, DEFAULT_BUFFER_SIZE) }
            } != null
        }.getOrDefault(false)

        runCatching {
            resolver.update(
                uri,
                ContentValues().apply { put(MediaStore.MediaColumns.IS_PENDING, 0) },
                null, null
            )
        }
        if (!written) runCatching { resolver.delete(uri, null, null) }
        return written
    }
}

/**
 * Ayni isimli bir dosya varsa ad degistirir: "video.mp4" -> "video (1).mp4".
 * Mevcut dosyanin uzerine yazmaz.
 */
fun benzersizAd(mevcutAdlar: List<String>, ad: String): String {
    if (ad !in mevcutAdlar) return ad
    val sonNokta = ad.lastIndexOf('.')
    val uzantili = sonNokta > 0
    val govde = if (uzantili) ad.substring(0, sonNokta) else ad
    val uzanti = if (uzantili) ad.substring(sonNokta + 1) else ""
    var sayac = 1
    while (true) {
        val aday = if (uzanti.isBlank()) "$govde ($sayac)" else "$govde ($sayac).$uzanti"
        if (aday !in mevcutAdlar) return aday
        sayac++
    }
}
