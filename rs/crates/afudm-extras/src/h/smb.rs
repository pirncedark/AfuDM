//! Agda paylasilan dosyalarin SMB (Windows `net share`) yasam dongusu.
//! Python: core/smb_paylasim.py (acik_paylasimlar, artiklari_temizle) ve app.py
//! (agda_paylas, _paylasim_kaynaklarini_temizle).
//! `net share .../GRANT:Everyone,READ` agdaki herkese okuma verir; kapatma ve acilis temizligi bu modulde.

use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};

use afudm_types::{AfuError, Result};

/// Python `ONEK`: yalniz bu onekli paylasimlar AfuDM'e aittir.
pub const ONEK: &str = "AfuDM_";

/// Python `KOK`: gecici paylasim klasoru.
pub fn kok() -> PathBuf {
    std::env::temp_dir().join("AfuDM-network-shares")
}

/// Paylasim olusturulmus dosya bilgisi. `unc` telefona/agdaki cihaza verilen yoldur.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SmbPaylasim {
    pub ad: String,
    pub hazirlik: PathBuf,
    pub unc: String,
}

/// `net` komutunu calistirir. Windows disinda None. Konsol penceresi acilmaz.
fn net(args: &[&str]) -> Option<Output> {
    if !cfg!(windows) {
        return None;
    }
    let mut komut = Command::new("net");
    komut
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        komut.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    komut.output().ok()
}

/// `net share` ciktisindan AfuDM_ onekli paylasim adlarini cikarir (Python `acik_paylasimlar` ayristirma kismi).
/// Her satirin ilk kelimesi bakilir; Turkce karakter ve bozuk kodlama satirlarina dokunmaz.
pub fn paylasim_adlari(cikti: &str) -> Vec<String> {
    cikti
        .lines()
        .filter_map(|satir| satir.split_whitespace().next())
        .filter(|ilk| ilk.starts_with(ONEK))
        .map(String::from)
        .collect()
}

/// Acik AfuDM_ paylasimlari. `net share` basarisizsa bos liste.
pub fn acik_paylasimlar() -> Vec<String> {
    match net(&["share"]) {
        Some(c) if c.status.success() => paylasim_adlari(&String::from_utf8_lossy(&c.stdout)),
        _ => Vec::new(),
    }
}

/// Acilista kalan AfuDM_ paylasimlarini kapatir ve gecici klasoru siler; kapatilan sayi.
/// Python `artiklari_temizle`.
pub fn artiklari_temizle() -> usize {
    let adlar = acik_paylasimlar();
    for ad in &adlar {
        let _ = net(&["share", ad, "/delete", "/y"]);
    }
    let _ = std::fs::remove_dir_all(kok());
    adlar.len()
}

/// Dosyanin KOPYASINI tokena ozel gecici klasore koyar ve `Everyone,READ` ile paylasir.
/// Python `agda_paylas` icindeki SMB kismi. Windows disinda ya da net basarisizsa Err;
/// bu durumda gecici klasor silinir ve HTTP baglantisi cagiran tarafta kalir.
pub fn paylas_olustur(token: &str, yol: &Path) -> Result<SmbPaylasim> {
    let ad = yol
        .file_name()
        .map(|s| s.to_string_lossy().into_owned())
        .ok_or_else(|| AfuError::Invalid("dosya adi yok".into()))?;
    let hazirlik = kok().join(token);
    let kopya = (|| -> std::io::Result<()> {
        std::fs::create_dir_all(&hazirlik)?;
        std::fs::copy(yol, hazirlik.join(&ad))?;
        Ok(())
    })();
    if let Err(e) = kopya {
        let _ = std::fs::remove_dir_all(&hazirlik);
        return Err(e.into());
    }
    let paylasim_ad = format!(
        "{ONEK}{}",
        token.replace('-', "").chars().take(12).collect::<String>()
    );
    let hedef = format!("{paylasim_ad}={}", hazirlik.display());
    match net(&["share", &hedef, "/GRANT:Everyone,READ"]) {
        Some(c) if c.status.success() => {
            let host = std::env::var("COMPUTERNAME").unwrap_or_else(|_| "127.0.0.1".into());
            Ok(SmbPaylasim {
                unc: format!(r"\\{host}\{paylasim_ad}\{ad}"),
                ad: paylasim_ad,
                hazirlik,
            })
        }
        Some(c) => {
            let _ = std::fs::remove_dir_all(&hazirlik);
            let metin = format!(
                "{} {}",
                String::from_utf8_lossy(&c.stderr),
                String::from_utf8_lossy(&c.stdout)
            );
            Err(AfuError::Engine(format!(
                "SMB paylasimi acilamadi ({})",
                metin.trim()
            )))
        }
        None => {
            let _ = std::fs::remove_dir_all(&hazirlik);
            Err(AfuError::Unavailable(
                "SMB paylasimi yalniz Windows'ta kullanilabilir".into(),
            ))
        }
    }
}

/// Paylasimi kapatir ve gecici kopyayi siler. Python `_paylasim_kaynaklarini_temizle`:
/// "bulunamadi" tipi cevap (paylasim zaten yok) hata sayilmaz. Donus: kalan sorunlar (bos = temiz).
pub fn paylas_kaldir(paylasim: &SmbPaylasim) -> Vec<String> {
    let mut sorunlar = Vec::new();
    if let Some(c) = net(&["share", &paylasim.ad, "/delete", "/y"]) {
        if !c.status.success() {
            let metin = format!(
                "{} {}",
                String::from_utf8_lossy(&c.stderr),
                String::from_utf8_lossy(&c.stdout)
            );
            let kucuk = metin.to_lowercase();
            let yok = ["does not exist", "not found", "no such", "bulunamad"]
                .iter()
                .any(|ifade| kucuk.contains(ifade));
            if !yok {
                sorunlar.push(format!("{}: {}", paylasim.ad, metin.trim()));
            }
        }
    }
    if let Err(e) = std::fs::remove_dir_all(&paylasim.hazirlik) {
        if e.kind() != std::io::ErrorKind::NotFound {
            sorunlar.push(format!("{}: {e}", paylasim.hazirlik.display()));
        }
    }
    sorunlar
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn net_share_ciktisi_sadece_afudm_adlarini_alir() {
        let cikti = "Paylaşım adı   Kaynak                 Açıklama\r\n\
-------------------------------------------------------------\r\n\
ADMIN$          C:\\Windows       Uzak Yönetim\r\n\
AfuDM_abc123def4 C:\\Temp\\x\r\n\
AfuDM_zz9        C:\\Temp\\y\r\n\
IPC$                              Uzak IPC\r\n\
The command completed successfully.\r\n";
        assert_eq!(
            paylasim_adlari(cikti),
            vec!["AfuDM_abc123def4".to_string(), "AfuDM_zz9".to_string()]
        );
    }

    #[test]
    fn bos_cikti_bos_liste() {
        assert!(paylasim_adlari("").is_empty());
    }

    #[test]
    fn kok_afudm_network_shares_adinda() {
        assert!(kok().ends_with("AfuDM-network-shares"));
    }
}
