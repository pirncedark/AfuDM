package com.afudm.afutube

object ShareLinkBuilder {
    private const val RELEASES = "https://github.com/pirncedark/AfuDM/releases"

    fun url(versionName: String): String = if (versionName.matches(Regex("\\d+\\.\\d+\\.\\d+"))) {
        "https://github.com/pirncedark/AfuDM/releases/download/afutube-v$versionName/AfuTube-universal.apk"
    } else RELEASES
}
