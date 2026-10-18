//! Ekip G1. Python: core/chrome_kurulum.py — AfuDM uzantisini Chrome'a ekleme yardimi.
//! Chrome Web Magazasi disi uzantiyi kendiliginden kurmaz; otomasyon Windows UI Automation betigiyle
//! (chrome_ekle.ps1, Python'daki BETIK ile birebir) yapilir. Betik stdout'a JSON satirlari yazar.

use afudm_types::Json;
use serde_json::{json, Value};
use std::io::{self, BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const BETIK_SABLONU: &str = include_str!("chrome_ekle.ps1");
/// Python: ADIMLAR — betigin raporladigi adim sirasi.
pub const ADIMLAR: [&str; 5] = ["sayfa", "gelistirici", "yukle", "klasor", "dogrula"];
const ZAMAN_ASIMI: Duration = Duration::from_secs(180);

/// Python: ADLAR — Chrome arayuz dili Windows dilinden farkli olabilir; iki dil de aranir.
fn adlar(anahtar: &str) -> &'static [&'static str] {
    match anahtar {
        "sayfa" => &["Uzantılar", "Extensions"],
        "gelistirici" => &["Geliştirici modu", "Developer mode"],
        "yukle" => &["Paketlenmemiş öğe yükle", "Load unpacked"],
        "adres" => &["Adres ve arama çubuğu", "Address and search bar"],
        _ => &[],
    }
}

/// Python: chrome_yolu — once App Paths kaydi, sonra bilinen klasorler.
pub fn chrome_yolu() -> Option<PathBuf> {
    #[cfg(windows)]
    {
        use winreg::enums::{HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE};
        use winreg::RegKey;
        let anahtar = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe";
        for kok in [HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE] {
            if let Ok(k) = RegKey::predef(kok).open_subkey(anahtar) {
                if let Ok(yol) = k.get_value::<String, _>("") {
                    let p = PathBuf::from(yol);
                    if !p.as_os_str().is_empty() && p.exists() {
                        return Some(p);
                    }
                }
            }
        }
    }
    for ortam in ["PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"] {
        if let Ok(taban) = std::env::var(ortam) {
            let aday = PathBuf::from(taban)
                .join("Google")
                .join("Chrome")
                .join("Application")
                .join("chrome.exe");
            if aday.exists() {
                return Some(aday);
            }
        }
    }
    None
}

/// Python: sayfayi_ac — bos sekme acar; chrome:// adresini betik yazar.
pub fn sayfayi_ac(ek_argumanlar: &[String]) -> Option<Child> {
    let chrome = chrome_yolu()?;
    Command::new(chrome)
        .args(ek_argumanlar)
        .arg("about:blank")
        .spawn()
        .ok()
}

/// Python: panoya_kopyala — `clip` komutuna UTF-16LE metin verir.
pub fn panoya_kopyala(metin: &str) -> bool {
    let mut komut = Command::new("clip");
    komut
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        komut.creation_flags(CREATE_NO_WINDOW);
    }
    let Ok(mut cocuk) = komut.spawn() else {
        return false;
    };
    if let Some(mut girdi) = cocuk.stdin.take() {
        let bayt: Vec<u8> = metin.encode_utf16().flat_map(u16::to_le_bytes).collect();
        let _ = girdi.write_all(&bayt);
    }
    cocuk.wait().is_ok_and(|s| s.success())
}

fn liste(anahtar: &str) -> String {
    adlar(anahtar)
        .iter()
        .map(|ad| format!("'{}'", ad.replace('\'', "''")))
        .collect::<Vec<_>>()
        .join(", ")
}

/// Python: _betik_dosyasi icerigi — yer tutucular doldurulmus betik metni.
pub fn betik_metni() -> String {
    BETIK_SABLONU
        .replace("__SAYFA__", &liste("sayfa"))
        .replace("__GELISTIRICI__", &liste("gelistirici"))
        .replace("__YUKLE__", &liste("yukle"))
        .replace("__ADRES__", &liste("adres"))
}

/// Python: _betik_dosyasi — betigi `data/chrome_ekle.ps1` olarak (UTF-8 BOM ile) yazar.
pub fn betik_dosyasi(data: &Path) -> io::Result<PathBuf> {
    std::fs::create_dir_all(data)?;
    let hedef = data.join("chrome_ekle.ps1");
    let mut icerik = vec![0xEF, 0xBB, 0xBF];
    icerik.extend_from_slice(betik_metni().as_bytes());
    std::fs::write(&hedef, icerik)?;
    Ok(hedef)
}

/// Python: OtomatikEkleme — arka planda calisan tek bir ekleme denemesi.
pub struct OtomatikEkleme {
    durum: Arc<Mutex<Json>>,
}

impl Default for OtomatikEkleme {
    fn default() -> Self {
        Self::new()
    }
}

impl OtomatikEkleme {
    pub fn new() -> Self {
        OtomatikEkleme {
            durum: Arc::new(Mutex::new(
                json!({"calisiyor": false, "adimlar": {}, "sonuc": "", "mesaj": ""}),
            )),
        }
    }

    pub fn durum(&self) -> Json {
        self.durum.lock().expect("durum kilidi").clone()
    }

    /// Python: baslat. `hedef_pid == -1`: yeni acilan Chrome surecinin PID'i kullanilir (test).
    /// Donus: false ise zaten calisiyor.
    pub fn baslat(
        &self,
        data: PathBuf,
        uzanti_klasoru: PathBuf,
        ek_argumanlar: Vec<String>,
        hedef_pid: i64,
    ) -> bool {
        {
            let mut d = self.durum.lock().expect("durum kilidi");
            if d["calisiyor"] == true {
                return false;
            }
            let adimlar: serde_json::Map<String, Json> = ADIMLAR
                .iter()
                .map(|a| (a.to_string(), json!("bekliyor")))
                .collect();
            *d = json!({"calisiyor": true, "adimlar": adimlar, "sonuc": "", "mesaj": ""});
        }
        let durum = Arc::clone(&self.durum);
        std::thread::spawn(move || {
            calis(&durum, &data, &uzanti_klasoru, &ek_argumanlar, hedef_pid);
            guncelle(&durum, |d| d["calisiyor"] = json!(false));
        });
        true
    }
}

fn guncelle(durum: &Mutex<Json>, f: impl FnOnce(&mut Json)) {
    if let Ok(mut d) = durum.lock() {
        f(&mut d);
    }
}

fn adim_yaz(durum: &Mutex<Json>, adim: &str, deger: &str) {
    guncelle(durum, |d| d["adimlar"][adim] = json!(deger));
}

fn calis(durum: &Mutex<Json>, data: &Path, klasor: &Path, ek: &[String], hedef_pid: i64) {
    if let Err(hata) = calis_ic(durum, data, klasor, ek, hedef_pid) {
        let mesaj: String = hata.chars().take(300).collect();
        guncelle(durum, |d| {
            d["sonuc"] = json!("hata");
            d["mesaj"] = json!(mesaj);
        });
    }
}

fn calis_ic(
    durum: &Mutex<Json>,
    data: &Path,
    klasor: &Path,
    ek: &[String],
    mut hedef_pid: i64,
) -> std::result::Result<(), String> {
    if chrome_yolu().is_none() {
        return Err("chrome_yok".into());
    }
    let islem = sayfayi_ac(ek);
    if hedef_pid == -1 {
        if let Some(c) = &islem {
            hedef_pid = i64::from(c.id());
        }
    }
    adim_yaz(durum, "sayfa", "calisiyor");
    let betik = betik_dosyasi(data).map_err(|e| e.to_string())?;
    let mut komut = Command::new("powershell");
    komut
        .args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"])
        .arg(&betik)
        .arg("-Klasor")
        .arg(klasor)
        .arg("-HedefPid")
        .arg(hedef_pid.max(0).to_string())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        komut.creation_flags(CREATE_NO_WINDOW);
    }
    let mut cocuk = komut.spawn().map_err(|e| e.to_string())?;
    let cocuk_kimlik = cocuk.id();
    // Zaman asimi: 180 sn dolarsa betik (ve alt surecleri) oldurulur; normal bitiste iptal edilir.
    let (iptal_tx, iptal_rx) = mpsc::channel::<()>();
    std::thread::spawn(move || {
        if let Err(mpsc::RecvTimeoutError::Timeout) = iptal_rx.recv_timeout(ZAMAN_ASIMI) {
            let _ = Command::new("taskkill")
                .args(["/PID", &cocuk_kimlik.to_string(), "/T", "/F"])
                .status();
        }
    });
    let mut son_hata = String::new();
    if let Some(cikti) = cocuk.stdout.take() {
        for satir in BufReader::new(cikti).lines().map_while(Result::ok) {
            let satir = satir.trim().to_string();
            if !satir.starts_with('{') {
                if !satir.is_empty() {
                    son_hata = satir.chars().take(300).collect();
                }
                continue;
            }
            let Ok(olay) = serde_json::from_str::<Value>(&satir) else {
                continue;
            };
            let adim = olay["adim"].as_str().unwrap_or("").to_string();
            let d = olay["durum"].as_str().unwrap_or("").to_string();
            adim_yaz(durum, &adim, &d);
            if d == "hata" {
                son_hata = olay["mesaj"].as_str().unwrap_or("").to_string();
            } else if let Some(sira) = ADIMLAR.iter().position(|a| *a == adim) {
                if let Some(sonraki) = ADIMLAR.get(sira + 1) {
                    adim_yaz(durum, sonraki, "calisiyor");
                }
            }
        }
    }
    let kod = cocuk.wait().map_err(|e| e.to_string())?;
    let _ = iptal_tx.send(());
    let basarili = kod.success();
    guncelle(durum, |d| {
        d["sonuc"] = json!(if basarili { "kuruldu" } else { "hata" });
        d["mesaj"] = json!(if basarili {
            String::new()
        } else {
            son_hata.clone()
        });
    });
    Ok(())
}

/// Python: bekle_bitsin — ekleme bitene (sonuc dolana) kadar bekler; en fazla `zaman_asimi`.
pub fn bekle_bitsin(ekleme: &OtomatikEkleme, zaman_asimi: Duration) -> Json {
    let son = Instant::now() + zaman_asimi;
    loop {
        let d = ekleme.durum();
        let bitti = d["calisiyor"] != true && d["sonuc"].as_str().is_some_and(|s| !s.is_empty());
        if bitti || Instant::now() >= son {
            return d;
        }
        std::thread::sleep(Duration::from_millis(500));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn betik_yer_tutucularini_doldurur() {
        let metin = betik_metni();
        assert!(!metin.contains("__"), "yer tutucu kaldi");
        assert!(metin.contains("'Uzantılar', 'Extensions'"));
        assert!(metin.contains("param([string]$Klasor"));
    }

    #[test]
    fn baslangic_durumu_bos() {
        let e = OtomatikEkleme::new();
        assert_eq!(e.durum()["calisiyor"], false);
        assert_eq!(e.durum()["sonuc"], "");
    }

    #[test]
    fn calisirken_ikinci_baslatma_reddedilir() {
        let e = OtomatikEkleme::new();
        guncelle(&e.durum, |d| d["calisiyor"] = json!(true));
        assert!(!e.baslat(PathBuf::new(), PathBuf::new(), vec![], 0));
    }

    #[test]
    fn bekle_bitsin_sonuc_hazirsa_hemen_doner() {
        let e = OtomatikEkleme::new();
        guncelle(&e.durum, |d| {
            d["sonuc"] = json!("hata");
            d["mesaj"] = json!("chrome_yok");
        });
        let s = bekle_bitsin(&e, Duration::from_secs(5));
        assert_eq!(s["mesaj"], "chrome_yok");
    }
}
