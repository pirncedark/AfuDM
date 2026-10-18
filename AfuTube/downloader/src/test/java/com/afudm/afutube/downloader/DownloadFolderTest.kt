package com.afudm.afutube.downloader

import org.junit.Assert.assertEquals
import org.junit.Test

class DownloadFolderTest {

    @Test
    fun gorunur_klasor_adi_afutube() {
        assertEquals("afutube", DownloadFolder.NAME)
        assertEquals("Download/afutube", DownloadFolder.RELATIVE_PATH)
    }

    @Test
    fun ad_kullanilmiyorsa_aynen_kalir() {
        assertEquals("video.mp4", benzersizAd(emptyList(), "video.mp4"))
    }

    @Test
    fun ayni_ad_varsa_sayac_ekler() {
        assertEquals("video (1).mp4", benzersizAd(listOf("video.mp4"), "video.mp4"))
        assertEquals("video (2).mp4", benzersizAd(listOf("video.mp4", "video (1).mp4"), "video.mp4"))
    }

    @Test
    fun uzantisi_yoksa_sadece_ad_degisir() {
        assertEquals("klasor (1)", benzersizAd(listOf("klasor"), "klasor"))
    }

    @Test
    fun noktali_gizli_dosya_uzanti_sanilmaz() {
        assertEquals(".env (1)", benzersizAd(listOf(".env"), ".env"))
    }

    @Test
    fun coklu_noktali_ad_sadece_son_uzantiyi_ayirir() {
        assertEquals("benim.videom (1).mp4", benzersizAd(listOf("benim.videom.mp4"), "benim.videom.mp4"))
    }
}
