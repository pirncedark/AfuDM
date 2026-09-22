package com.afudm.afutube.updater

import android.content.Context
import com.yausername.youtubedl_android.YoutubeDL
import com.yausername.youtubedl_android.YoutubeDL.UpdateChannel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * yt-dlp extractor güncelleme modülü.
 *
 * yt-dlp "stable" sürümler site değişikliklerinde geride kalabilir;
 * nightly kanalı anlık düzeltmeler alır.
 *
 * Kullanım:
 *   ExtractorUpdater.checkAndUpdate(context, channel = Channel.NIGHTLY)
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
     * @param channel STABLE (önerilen) veya NIGHTLY
     */
    suspend fun checkAndUpdate(
        context : Context,
        channel : Channel = Channel.STABLE
    ): UpdateResult = withContext(Dispatchers.IO) {
        val oldVer = currentVersion(context)
        val ytChannel = if (channel == Channel.NIGHTLY) UpdateChannel.NIGHTLY else UpdateChannel.STABLE

        val status = runCatching {
            YoutubeDL.getInstance().updateYoutubeDL(context, ytChannel)
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
