package com.afudm.afutube.updater

import android.content.Context
import com.yausername.youtubedl_android.YoutubeDL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * yt-dlp extractor güncelleme modülü.
 *
 * Kullanım:
 *   ExtractorUpdater.checkAndUpdate(context)
 */
object ExtractorUpdater {

    enum class Channel { STABLE, NIGHTLY }

    data class UpdateResult(
        val updated    : Boolean,
        val oldVersion : String,
        val newVersion : String,
        val error      : String = ""
    )

    /** Mevcut yt-dlp sürümünü döndürür */
    suspend fun currentVersion(context: Context): String = withContext(Dispatchers.IO) {
        runCatching {
            YoutubeDL.getInstance().version(context) ?: "bilinmiyor"
        }.getOrElse { "hata: ${it.localizedMessage}" }
    }

    /**
     * Güncelleme kontrol et ve yükle.
     */
    suspend fun checkAndUpdate(
        context : Context,
        channel : Channel = Channel.STABLE
    ): UpdateResult = withContext(Dispatchers.IO) {
        val oldVer = currentVersion(context)

        val status = runCatching {
            YoutubeDL.getInstance().updateYoutubeDL(context)
        }.getOrElse {
            return@withContext UpdateResult(
                updated    = false,
                oldVersion = oldVer,
                newVersion = oldVer,
                error      = it.localizedMessage ?: "Güncelleme başarısız"
            )
        }

        val newVer = currentVersion(context)
        UpdateResult(
            updated    = status == YoutubeDL.UpdateStatus.DONE,
            oldVersion = oldVer,
            newVersion = newVer
        )
    }
}
