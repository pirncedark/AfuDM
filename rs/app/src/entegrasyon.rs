//! Windows kabuk entegrasyonlari. Python karsiliklari:
//! - torrent/magnet: core/iliskilendir.py (HKCU\Software\Classes)
//! - afudm:// protokolu: core/windows_integration.py ("protocol")
//! - acilista calisma: core/baslangic.py (Baslangic klasorundeki .lnk)
//!
//! Hepsi kullanici duzeyi (yonetici gerekmez). Yalniz ilk degisiklikte eski
//! deger yedeklenir; geri alma yedekten yapilir.

use std::fs;
use std::io;
use std::os::windows::process::CommandExt;
use std::path::PathBuf;
use std::process::Command;

use winreg::enums::{HKEY_CURRENT_USER, KEY_SET_VALUE};
use winreg::RegKey;

const KOK: &str = r"Software\Classes";
const TORRENT_UZANTI: &str = ".torrent";
const TORRENT_PROGID: &str = "AfuDM.torrent";
const MAGNET: &str = "magnet";
const PROTOKOL: &str = "afudm";
const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const KISAYOL_ADI: &str = "AfuDM.lnk";
const KISAYOL_ACIKLAMA: &str = "AfuDM — indirme yoneticisi";

/// Python baslangic._BETIK ile ayni: WScript.Shell ile .lnk yazar.
const BETIK: &str = r#"
param([string]$KisayolYolu,[string]$Hedef,[string]$Argumanlar,[string]$CalismaKlasoru,[string]$Aciklama,[string]$Simge)
$ErrorActionPreference = "Stop"
$kabuk = New-Object -ComObject WScript.Shell
$kisayol = $kabuk.CreateShortcut($KisayolYolu)
$kisayol.TargetPath = $Hedef
if ($Argumanlar) { $kisayol.Arguments = $Argumanlar }
$kisayol.WorkingDirectory = $CalismaKlasoru
$kisayol.Description = $Aciklama
if ($Simge) { $kisayol.IconLocation = $Simge }
$kisayol.Save()
"#;

fn hkcu() -> RegKey {
    RegKey::predef(HKEY_CURRENT_USER)
}

fn anahtar(alt: &str) -> String {
    format!(r"{KOK}\{alt}")
}

fn oku(alt: &str, ad: &str) -> Option<String> {
    hkcu()
        .open_subkey(anahtar(alt))
        .ok()?
        .get_value::<String, _>(ad)
        .ok()
}

fn yaz(alt: &str, deger: &str, ad: &str) -> io::Result<()> {
    let (k, _) = hkcu().create_subkey(anahtar(alt))?;
    k.set_value(ad, &deger)
}

fn sil_deger(alt: &str, ad: &str) {
    if let Ok(k) = hkcu().open_subkey_with_flags(anahtar(alt), KEY_SET_VALUE) {
        let _ = k.delete_value(ad);
    }
}

fn agac_sil(alt: &str) {
    let _ = hkcu().delete_subkey_all(anahtar(alt));
}

/// Kabugun calistirilabilir komutu: `"AfuDM.exe" "%1"`.
pub fn komut() -> io::Result<String> {
    Ok(format!("\"{}\" \"%1\"", std::env::current_exe()?.display()))
}

// --- torrent / magnet --------------------------------------------------------

fn torrent_ac(komut: &str) -> io::Result<()> {
    yaz(TORRENT_PROGID, "AfuDM Torrent Dosyasi", "")?;
    yaz(&format!("{TORRENT_PROGID}\\shell\\open\\command"), komut, "")?;
    if oku(TORRENT_PROGID, "AfuDM_OncekiVarMi").is_none() {
        match oku(TORRENT_UZANTI, "") {
            Some(eski) if eski != TORRENT_PROGID => {
                yaz(TORRENT_PROGID, "1", "AfuDM_OncekiVarMi")?;
                yaz(TORRENT_PROGID, &eski, "AfuDM_OncekiProgId")?;
            }
            _ => yaz(TORRENT_PROGID, "0", "AfuDM_OncekiVarMi")?,
        }
    }
    yaz(TORRENT_UZANTI, TORRENT_PROGID, "")?;
    yaz(&format!("{TORRENT_UZANTI}\\OpenWithProgids"), "", TORRENT_PROGID)
}

fn torrent_kapat() {
    let Some(onceki) = oku(TORRENT_PROGID, "AfuDM_OncekiVarMi") else {
        return;
    };
    if onceki == "1" {
        let eski = oku(TORRENT_PROGID, "AfuDM_OncekiProgId").unwrap_or_default();
        let _ = yaz(TORRENT_UZANTI, &eski, "");
    } else {
        sil_deger(TORRENT_UZANTI, "");
    }
    sil_deger(&format!("{TORRENT_UZANTI}\\OpenWithProgids"), TORRENT_PROGID);
    agac_sil(TORRENT_PROGID);
}

fn magnet_ac(komut: &str) -> io::Result<()> {
    if oku(MAGNET, "AfuDM_OncekiVarMi").is_none() {
        let eski_komut = oku(&format!("{MAGNET}\\shell\\open\\command"), "");
        let eski_aciklama = oku(MAGNET, "");
        if eski_komut.is_some() || eski_aciklama.is_some() {
            yaz(MAGNET, "1", "AfuDM_OncekiVarMi")?;
            if let Some(k) = eski_komut {
                yaz(MAGNET, &k, "AfuDM_OncekiKomut")?;
            }
            if let Some(a) = eski_aciklama {
                yaz(MAGNET, &a, "AfuDM_OncekiAciklama")?;
            }
        } else {
            yaz(MAGNET, "0", "AfuDM_OncekiVarMi")?;
        }
    }
    yaz(MAGNET, "URL:Magnet Baglantisi", "")?;
    yaz(MAGNET, "", "URL Protocol")?;
    yaz(&format!("{MAGNET}\\shell\\open\\command"), komut, "")
}

fn magnet_kapat() {
    let Some(onceki) = oku(MAGNET, "AfuDM_OncekiVarMi") else {
        return;
    };
    if onceki == "1" {
        match oku(MAGNET, "AfuDM_OncekiAciklama") {
            Some(a) => {
                let _ = yaz(MAGNET, &a, "");
            }
            None => sil_deger(MAGNET, ""),
        }
        match oku(MAGNET, "AfuDM_OncekiKomut") {
            Some(k) => {
                let _ = yaz(&format!("{MAGNET}\\shell\\open\\command"), &k, "");
            }
            None => agac_sil(&format!("{MAGNET}\\shell\\open\\command")),
        }
        sil_deger(MAGNET, "AfuDM_OncekiKomut");
        sil_deger(MAGNET, "AfuDM_OncekiAciklama");
        sil_deger(MAGNET, "AfuDM_OncekiVarMi");
    } else {
        agac_sil(MAGNET);
    }
}

/// .torrent ve magnet'i AfuDM'e baglar. Iki kez cagrilmak guvenlidir.
pub fn iliskilendir_ac() -> io::Result<()> {
    let k = komut()?;
    torrent_ac(&k)?;
    magnet_ac(&k)
}

pub fn iliskilendir_kapat() {
    torrent_kapat();
    magnet_kapat();
}

/// Python iliskilendir.durum() sadelestirilmis hali: iki kayit da bizim komutumuzu gosteriyor mu.
pub fn iliskilendirme_durumu() -> (bool, bool) {
    let Ok(k) = komut() else {
        return (false, false);
    };
    let torrent = oku(&format!("{TORRENT_PROGID}\\shell\\open\\command"), "").as_deref() == Some(k.as_str());
    let magnet = oku(&format!("{MAGNET}\\shell\\open\\command"), "").as_deref() == Some(k.as_str());
    (torrent, magnet)
}

// --- afudm:// protokolu -------------------------------------------------------

pub fn protokol_ac() -> io::Result<()> {
    let k = komut()?;
    yaz(PROTOKOL, "URL:AfuDM Download", "")?;
    yaz(PROTOKOL, "", "URL Protocol")?;
    yaz(&format!("{PROTOKOL}\\shell\\open\\command"), &k, "")
}

pub fn protokol_kapat() {
    agac_sil(PROTOKOL);
}

pub fn protokol_kayitli() -> bool {
    let Ok(k) = komut() else {
        return false;
    };
    oku(&format!("{PROTOKOL}\\shell\\open\\command"), "").as_deref() == Some(k.as_str())
}

// --- acilista calisma ---------------------------------------------------------

/// Baslangic klasoru (Python _startup_klasoru): once kayit defterindeki gercek yol.
fn baslangic_klasoru() -> PathBuf {
    let yol = hkcu()
        .open_subkey(r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        .ok()
        .and_then(|k| k.get_value::<String, _>("Startup").ok())
        .map(|d| PathBuf::from(d.replace("%USERPROFILE%", &std::env::var("USERPROFILE").unwrap_or_default())));
    match yol {
        Some(p) if p.is_dir() => p,
        _ => std::env::var_os("APPDATA")
            .map(|a| PathBuf::from(a).join(r"Microsoft\Windows\Start Menu\Programs\Startup"))
            .unwrap_or_else(|| PathBuf::from(".")),
    }
}

pub fn baslangic_kisayolu() -> PathBuf {
    baslangic_klasoru().join(KISAYOL_ADI)
}

pub fn baslangic_acik() -> bool {
    baslangic_kisayolu().is_file()
}

fn powershell_calistir(args: &[&str], betik_dosyasi: Option<&std::path::Path>) -> io::Result<String> {
    let mut komut = Command::new("powershell");
    komut.args(["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass"]);
    if let Some(dosya) = betik_dosyasi {
        komut.arg("-File").arg(dosya).args(args);
    } else {
        komut.arg("-Command").args(args);
    }
    let cikti = komut.creation_flags(CREATE_NO_WINDOW).output()?;
    if !cikti.status.success() {
        let hata = String::from_utf8_lossy(&cikti.stderr);
        return Err(io::Error::other(format!("kisayol komutu basarisiz: {}", hata.trim())));
    }
    Ok(String::from_utf8_lossy(&cikti.stdout).trim().to_string())
}

/// Baslangic kisayolunu yazar. `ek_arguman` acilis bayragi (ornek: "--tepside").
pub fn baslangic_ac(ek_arguman: &str) -> io::Result<()> {
    let exe = std::env::current_exe()?;
    let kisayol = baslangic_kisayolu();
    let exe_str = exe.display().to_string();
    if kisayol.is_file() {
        let mevcut = powershell_calistir(
            &[&format!(
                "$k = (New-Object -ComObject WScript.Shell).CreateShortcut('{}'); [Console]::Out.Write($k.Arguments)",
                kisayol.display().to_string().replace('\'', "''")
            )],
            None,
        )
        .unwrap_or_default();
        if mevcut == ek_arguman {
            return Ok(());
        }
    }
    fs::create_dir_all(baslangic_klasoru())?;
    let betik = std::env::temp_dir().join("afudm_kisayol.ps1");
    fs::write(&betik, BETIK)?;
    let sonuc = powershell_calistir(
        &[
            "-KisayolYolu",
            &kisayol.display().to_string(),
            "-Hedef",
            &exe_str,
            "-Argumanlar",
            ek_arguman,
            "-CalismaKlasoru",
            &exe.parent().map(|p| p.display().to_string()).unwrap_or_default(),
            "-Aciklama",
            KISAYOL_ACIKLAMA,
            "-Simge",
            &exe_str,
        ],
        Some(&betik),
    );
    let _ = fs::remove_file(&betik);
    sonuc.map(|_| ())
}

pub fn baslangic_kapat() -> io::Result<()> {
    match fs::remove_file(baslangic_kisayolu()) {
        Ok(()) => Ok(()),
        Err(e) if e.kind() == io::ErrorKind::NotFound => Ok(()),
        Err(e) => Err(e),
    }
}
