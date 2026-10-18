//! Kullaniciya giden hata metinleri ve dil secimi. Port of video/ytdlp.py (_HATA_CUMLERI,
//! kullanici_hata, anlasilir_hata) ve core/lang.py'nin video ile ilgili anahtarlari.
//! Ham yt-dlp metni HER ZAMAN korunur (`ham_hata`); ekrana tek cumle gider.

/// Python lang.system_language(): Windows arayuz dili Turkce mi?
#[cfg(windows)]
fn sistem_tr_mi() -> bool {
    #[link(name = "kernel32")]
    extern "system" {
        fn GetUserDefaultUILanguage() -> u16;
    }
    // SAFETY: GetUserDefaultUILanguage parametresiz, yalniz bir u16 dondurur.
    let lcid = unsafe { GetUserDefaultUILanguage() };
    (lcid & 0x3FF) == 0x1F
}

#[cfg(not(windows))]
fn sistem_tr_mi() -> bool {
    false
}

/// Python lang.resolve(): "tr" / "en" aynen; "auto" ya da bilinmeyen -> sistem dili.
pub(crate) fn tr_mi(dil: &str) -> bool {
    match dil.trim().to_lowercase().as_str() {
        "tr" => true,
        "en" => false,
        _ => sistem_tr_mi(),
    }
}

/// Python lang.t(anahtar, dil) — yalniz video icin gereken anahtarlar. Yoksa anahtar doner.
pub(crate) fn lang_t(anahtar: &str, dil: &str) -> String {
    let tr = tr_mi(dil);
    let metin = match anahtar {
        "err.needFfmpeg" => {
            if tr {
                "Bu video sesi ve görüntüyü ayrı gönderiyor; birleştirmek için ffmpeg gerekiyor. Ayarlar'dan gelişmiş video desteğini indir."
            } else {
                "This video sends audio and video separately; ffmpeg is needed to join them. Download the advanced video support from Settings."
            }
        }
        "err.needFfmpegAudio" => {
            if tr {
                "mp3'e çevirmek için ffmpeg gerekiyor. Ayarlar'dan gelişmiş video desteğini indir; o zamana kadar ses kaynaktaki biçimiyle iner."
            } else {
                "ffmpeg is needed to convert to mp3. Download the advanced video support from Settings; until then the audio is saved in its original format."
            }
        }
        "note.ffmpegEmbedSkipped" => {
            if tr {
                "ffmpeg bulunamadigi icin istenen video gomme islemleri uygulanamadi."
            } else {
                "ffmpeg was not found, so the requested video embedding operations were skipped."
            }
        }
        _ => return anahtar.to_string(),
    };
    metin.to_string()
}

/// (ipuclari, (tr, en)) — SIRA ONEMLI: en ozel ipucu once denenir.
const HATA_CUMLERI: &[(&[&str], (&str, &str))] = &[
    (
        &["not a bot", "sign in to confirm", "confirm you"],
        (
            "Bot kontrolu istiyor; site oturumuyla tekrar deneyin.",
            "The site wants a bot check; sign in on the site and try again.",
        ),
    ),
    (
        &["unavailable", "does not exist", "no such video"],
        (
            "Video bulunamadi; adresi kontrol edip baska bir video deneyin.",
            "Video not found; check the link and try another video.",
        ),
    ),
    (
        &[
            "has been removed",
            "removed by the uploader",
            "video was removed",
        ],
        (
            "Video kaldirilmis; baska bir video deneyin.",
            "This video was removed; try another video.",
        ),
    ),
    (
        &[
            "private",
            "sign in if you",
            "members-only",
            "join this channel",
        ],
        (
            "Video gizli; siteye giris yapip tekrar deneyin.",
            "This video is private; sign in on the site and try again.",
        ),
    ),
    (
        &["age-restricted", "age restricted", "confirm your age"],
        (
            "Video yas sinirli; siteye giris yapip tekrar deneyin.",
            "This video is age restricted; sign in on the site and try again.",
        ),
    ),
    (
        &[
            "not made this video available",
            "not available in your country",
            "blocked it in your country",
            "geo restricted",
            "geo-restricted",
        ],
        (
            "Video bu bolgede kapali; VPN kullanip tekrar deneyin.",
            "This video is blocked in your country; use a VPN and try again.",
        ),
    ),
    (
        &["429", "too many requests", "rate limit"],
        (
            "Cok fazla istek gonderildi; biraz bekleyip tekrar deneyin.",
            "Too many requests; wait a moment and try again.",
        ),
    ),
    (
        &["403", "forbidden"],
        (
            "Site erisimi engelledi; baglantiyi yeniden kurup tekrar deneyin.",
            "The site blocked access; renew the connection and try again.",
        ),
    ),
    (
        &[
            "is live",
            "live event",
            "premieres in",
            "post-live",
            "will begin in",
        ],
        (
            "Video canli yayinda; yayin bitince tekrar indirin.",
            "This video is live; download it after the stream ends.",
        ),
    ),
    (
        &[
            "500",
            "502",
            "503",
            "504",
            "internal server error",
            "bad gateway",
            "service unavailable",
            "timed out",
            "timeout",
            "connection",
            "unable to connect",
            "temporary failure",
            "name resolution",
            "getaddrinfo",
            "network is unreachable",
            "remote end closed",
            "ssl",
            "fragmented",
        ],
        (
            "Baglantiyi kuramadik; interneti kontrol edip tekrar deneyin.",
            "Could not open the connection; check your internet and try again.",
        ),
    ),
];

const HATA_VARSILAN: (&str, &str) = (
    "Video indirilemedi; adresi kontrol edip tekrar deneyin.",
    "Could not download the video; check the link and try again.",
);

/// Python VideoJob.kullanici_hata(): ham hata varsa ipucuna gore tek cumle; yoksa `error` olduğu gibi.
pub(crate) fn kullanici_hata(ham_hata: &str, error: &str, dil: &str) -> String {
    if ham_hata.is_empty() || error.is_empty() {
        return error.to_string();
    }
    if error != ham_hata {
        return error.to_string(); // zaten anlasilir metne cevrildi (ffmpeg notu)
    }
    let kucuk = ham_hata.to_lowercase();
    let tr = tr_mi(dil);
    for (ipuclari, (tr_metin, en_metin)) in HATA_CUMLERI {
        if ipuclari.iter().any(|ipuc| kucuk.contains(ipuc)) {
            let secilen = if tr { tr_metin } else { en_metin };
            return secilen.to_string();
        }
    }
    let (tr_metin, en_metin) = HATA_VARSILAN;
    let secilen = if tr { tr_metin } else { en_metin };
    secilen.to_string()
}

#[cfg(test)]
mod testler {
    use super::*;

    #[test]
    fn ham_hata_gizlenir_ipucuna_gore_cumle_secilir() {
        let ham = "ERROR: [youtube] abc: Sign in to confirm you're not a bot";
        assert_eq!(
            kullanici_hata(ham, ham, "tr"),
            "Bot kontrolu istiyor; site oturumuyla tekrar deneyin."
        );
        assert_eq!(
            kullanici_hata(ham, ham, "en"),
            "The site wants a bot check; sign in on the site and try again."
        );
    }

    #[test]
    fn bilinmeyen_hata_varsayilan_cumle() {
        assert_eq!(
            kullanici_hata("garip bir sey", "garip bir sey", "tr"),
            "Video indirilemedi; adresi kontrol edip tekrar deneyin."
        );
    }

    #[test]
    fn ffmpeg_notu_oldugu_gibi_gecer() {
        let not = lang_t("note.ffmpegEmbedSkipped", "en");
        assert_eq!(kullanici_hata("", &not, "en"), not);
        assert_eq!(kullanici_hata("", "", "en"), "");
    }

    #[test]
    fn acik_dil_secimi() {
        assert!(tr_mi("tr"));
        assert!(!tr_mi("EN"));
        assert!(lang_t("err.needFfmpeg", "tr").starts_with("Bu video"));
        assert_eq!(lang_t("anahtar.yok", "tr"), "anahtar.yok");
    }
}
