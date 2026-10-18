//! Ekip G1. Python: core/guncelleme.py + app.py guncelleme_* (kontrol, indir, durum, otomatik, son_kontrol, uygula).
//! GitHub Releases'ten zip + sha256 indirir, dogrular, uygulama betigini yazip baslatir.
//! Zip duzeni (2.9.x kurulum betigi icin sart): `AfuDM-v<surum>-win64.zip` icinde `AfuDM/AfuDM.exe`.

use afudm_types::{Json, JsonMap, Result, Store};
use regex::Regex;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

pub const VARSAYILAN_API: &str = "https://api.github.com/repos/pirncedark/AfuDM/releases/latest";
/// Indirme yalniz bu depodaki yayin dosyalarindan yapilir.
pub const IZINLI_ONEK: &str = "https://github.com/pirncedark/AfuDM/releases/download/";
/// Python: surum.SURUM. Rust surumu workspace surumudur.
pub const MEVCUT_SURUM: &str = env!("CARGO_PKG_VERSION");
const ZAMAN_ASIMI: Duration = Duration::from_secs(10);
const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const HATA_KONTROL: &str = "Güncelleme denetlenemedi. İnternet bağlantını kontrol et.";
const HATA_INDIR: &str = "Güncelleme indirilemedi veya dosya bozuk.";
const UYGULA_SABLONU: &str = include_str!("uygula.ps1");

/// Python: _parcala. "v3.0.1" -> [3,0,1]; gecersizse None (Python ValueError).
pub fn parcala(s: &str) -> Option<Vec<u64>> {
    let t = s.trim();
    let t = t.strip_prefix('v').unwrap_or(t);
    let gecerli = !t.is_empty()
        && t.split('.')
            .all(|p| !p.is_empty() && p.bytes().all(|b| b.is_ascii_digit()));
    if !gecerli {
        return None;
    }
    t.split('.').map(|p| p.parse().ok()).collect()
}

/// Python: guncelleme.kontrol(). GitHub'dan son yayini ister.
pub fn kontrol(api_url: &str) -> Json {
    match json_al(api_url) {
        Ok(veri) => kontrol_verisinden(&veri, MEVCUT_SURUM),
        Err(_) => json!({"ok": false, "hata": HATA_KONTROL}),
    }
}

/// GitHub yanitindan (`releases/latest` JSON'u) guncelleme bilgisi cikarir.
pub fn kontrol_verisinden(veri: &Json, mevcut: &str) -> Json {
    match yayini_degerlendir(veri, mevcut) {
        Ok(sonuc) => sonuc,
        Err(_) => json!({"ok": false, "hata": HATA_KONTROL}),
    }
}

fn yayini_degerlendir(veri: &Json, mevcut: &str) -> std::result::Result<Json, String> {
    if truthy(&veri["draft"]) || truthy(&veri["prerelease"]) {
        return Ok(
            json!({"ok": true, "var": false, "mevcut": mevcut, "yeni": mevcut,
            "notlar": "", "zip_url": "", "sha_url": ""}),
        );
    }
    let etiket = veri["tag_name"].as_str().unwrap_or("");
    let yeni = etiket.strip_prefix('v').unwrap_or(etiket).to_string();
    let mut assets: BTreeMap<String, String> = BTreeMap::new();
    for a in veri["assets"].as_array().map(Vec::as_slice).unwrap_or(&[]) {
        if let (Some(ad), Some(url)) = (a["name"].as_str(), a["browser_download_url"].as_str()) {
            assets.insert(ad.to_string(), url.to_string());
        }
    }
    let zip_ad = format!("AfuDM-v{yeni}-win64.zip");
    let (Some(zip_url), Some(sha_url)) =
        (assets.get(&zip_ad), assets.get(&format!("{zip_ad}.sha256")))
    else {
        return Err("Yayin dosyalari bulunamadi".into());
    };
    if !zip_url.starts_with(IZINLI_ONEK) || !sha_url.starts_with(IZINLI_ONEK) {
        return Err("Yayin dosyalari bulunamadi".into());
    }
    let yeni_p = parcala(&yeni).ok_or("Gecersiz surum")?;
    let mevcut_p = parcala(mevcut).ok_or("Gecersiz surum")?;
    let zip_size = veri["assets"]
        .as_array()
        .and_then(|a| {
            a.iter()
                .find(|a| a["name"].as_str() == Some(zip_ad.as_str()))
        })
        .and_then(|a| a["size"].as_u64());
    let notlar: String = veri["body"]
        .as_str()
        .unwrap_or("")
        .chars()
        .take(600)
        .collect();
    Ok(
        json!({"ok": true, "var": yeni_p > mevcut_p, "mevcut": mevcut, "yeni": yeni,
        "notlar": notlar, "zip_url": zip_url, "sha_url": sha_url, "zip_size": zip_size}),
    )
}

/// Python: indir_ve_dogrula. Zip'i indirir, sha256'yi dogrular, `data/guncelleme/yeni`'ye acar,
/// `hazir.json` yazar. Donus: {"ok": true, "yol": ...} ya da {"ok": false, "hata": ...}.
pub fn indir_ve_dogrula(bilgi: &Json, data: &Path, ilerleme: Option<&dyn Fn(u64, u64)>) -> Json {
    indir_ve_dogrula_onekli(bilgi, data, ilerleme, IZINLI_ONEK)
}

/// `indir_ve_dogrula` ile ayni; izinli onek parametre (testte yerel sunucu icin). Uretimde IZINLI_ONEK.
pub fn indir_ve_dogrula_onekli(
    bilgi: &Json,
    data: &Path,
    ilerleme: Option<&dyn Fn(u64, u64)>,
    onek: &str,
) -> Json {
    let hedef = data.join("guncelleme");
    let _ = fs::remove_file(hedef.join("hazir.json"));
    let mut zip_path = hedef.join("AfuDM-guncelleme.zip");
    match adimlar(bilgi, &hedef, &mut zip_path, ilerleme, onek) {
        Ok(sonuc) => sonuc,
        Err(_) => {
            let _ = fs::remove_file(&zip_path);
            json!({"ok": false, "hata": HATA_INDIR})
        }
    }
}

fn adimlar(
    bilgi: &Json,
    hedef: &Path,
    zip_path: &mut PathBuf,
    ilerleme: Option<&dyn Fn(u64, u64)>,
    onek: &str,
) -> std::result::Result<Json, String> {
    if !truthy(&bilgi["ok"]) || !truthy(&bilgi["var"]) {
        return Err("bilgi yok".into());
    }
    for anahtar in ["zip_url", "sha_url"] {
        if !bilgi[anahtar].as_str().unwrap_or("").starts_with(onek) {
            return Err("Untrusted release URL".into());
        }
    }
    let yeni_ham = bilgi["yeni"].as_str().unwrap_or("");
    let yeni_p = parcala(yeni_ham).ok_or("Gecersiz surum")?;
    let surum_yeni = yeni_p
        .iter()
        .map(u64::to_string)
        .collect::<Vec<_>>()
        .join(".");
    if yeni_p <= parcala(MEVCUT_SURUM).ok_or("Gecersiz surum")? {
        return Err("Update must be newer".into());
    }
    *zip_path = hedef.join(format!("AfuDM-v{surum_yeni}-win64.zip"));
    fs::create_dir_all(hedef).map_err(|e| e.to_string())?;
    let zip_url = bilgi["zip_url"].as_str().unwrap_or("");
    let sha_url = bilgi["sha_url"].as_str().unwrap_or("");
    indir(
        zip_url,
        zip_path.as_path(),
        ilerleme,
        bilgi["zip_size"].as_u64(),
    )?;

    let sha_metin = sha_metni_al(sha_url)?;
    let re = Regex::new(r"^\s*([0-9a-fA-F]{64})\s+(.+?)\s*$").map_err(|e| e.to_string())?;
    let eslesme = re.captures(&sha_metin).ok_or("sha bicimi")?;
    let ad = zip_path
        .as_path()
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("");
    if &eslesme[2] != ad {
        return Err("sha dosya adi".into());
    }
    let beklenen = eslesme[1].to_ascii_lowercase();
    let zip_bytes = fs::read(zip_path.as_path()).map_err(|e| e.to_string())?;
    if format!("{:x}", Sha256::digest(&zip_bytes)) != beklenen {
        let _ = fs::remove_file(zip_path.as_path());
        return Ok(json!({"ok": false, "hata": "Güncelleme dosyası doğrulanamadı."}));
    }

    let mut arsiv =
        zip::ZipArchive::new(fs::File::open(zip_path.as_path()).map_err(|e| e.to_string())?)
            .map_err(|e| e.to_string())?;
    for i in 0..arsiv.len() {
        let girdi = arsiv.by_index(i).map_err(|e| e.to_string())?;
        if !guvenli_zip_yolu(girdi.name()) {
            return Err("guvensiz zip yolu".into());
        }
    }
    let yeni = hedef.join("yeni");
    if yeni.exists() {
        fs::remove_dir_all(&yeni).map_err(|e| e.to_string())?;
    }
    fs::create_dir_all(&yeni).map_err(|e| e.to_string())?;
    arsiv.extract(&yeni).map_err(|e| e.to_string())?;
    if !yeni.join("AfuDM").join("AfuDM.exe").is_file() {
        return Err("AfuDM.exe yok".into());
    }
    let paket = yeni.join("AfuDM");
    let dosyalar = tarama(&paket).map_err(|e| e.to_string())?;
    let kayit = json!({"surum": surum_yeni, "dosyalar": dosyalar});
    fs::write(hedef.join("hazir.json"), kayit.to_string()).map_err(|e| e.to_string())?;
    Ok(json!({"ok": true, "yol": paket.to_string_lossy()}))
}

/// Python: indir() — ilerleme geri cagrili parca parca indirme.
fn indir(
    url: &str,
    hedef: &Path,
    ilerleme: Option<&dyn Fn(u64, u64)>,
    beklenen: Option<u64>,
) -> std::result::Result<(), String> {
    let mut yanit = istek(url)?;
    let uzunluk: Option<u64> = yanit
        .headers()
        .get("content-length")
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.trim().parse().ok());
    let sinir = match (beklenen, uzunluk) {
        (Some(a), Some(b)) => Some(a.min(b)),
        (a, b) => a.or(b),
    };
    let toplam = beklenen.or(uzunluk).unwrap_or(0);
    let mut out = fs::File::create(hedef).map_err(|e| e.to_string())?;
    let mut okuyucu = yanit.body_mut().as_reader();
    let mut tampon = vec![0u8; 128 * 1024];
    let mut inen = 0u64;
    loop {
        let n = okuyucu.read(&mut tampon).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        let yeni = inen.checked_add(n as u64).ok_or("indirme boyutu tasti")?;
        if sinir.is_some_and(|s| yeni > s) {
            return Err("indirme beklenen boyutu asiyor".into());
        }
        out.write_all(&tampon[..n]).map_err(|e| e.to_string())?;
        inen = yeni;
        if let Some(f) = ilerleme {
            f(inen, toplam);
        }
    }
    Ok(())
}

/// Python: sha dosyasi en fazla 4096 bayt, yalniz ASCII okunur.
fn sha_metni_al(url: &str) -> std::result::Result<String, String> {
    let mut yanit = istek(url)?;
    let mut tampon = Vec::new();
    yanit
        .body_mut()
        .as_reader()
        .take(4096)
        .read_to_end(&mut tampon)
        .map_err(|e| e.to_string())?;
    if !tampon.is_ascii() {
        return Err("ascii degil".into());
    }
    String::from_utf8(tampon).map_err(|e| e.to_string())
}

fn ajan() -> ureq::Agent {
    let yapi = ureq::Agent::config_builder()
        .timeout_connect(Some(ZAMAN_ASIMI))
        .timeout_recv_response(Some(ZAMAN_ASIMI))
        .timeout_recv_body(Some(Duration::from_secs(15 * 60)))
        .build();
    ureq::Agent::new_with_config(yapi)
}

fn istek(url: &str) -> std::result::Result<ureq::http::Response<ureq::Body>, String> {
    ajan()
        .get(url)
        .header("User-Agent", format!("AfuDM/{MEVCUT_SURUM}"))
        .header("Accept", "application/vnd.github+json")
        .call()
        .map_err(|e| e.to_string())
}

fn json_al(url: &str) -> std::result::Result<Json, String> {
    let mut yanit = istek(url)?;
    let metin = yanit
        .body_mut()
        .read_to_string()
        .map_err(|e| e.to_string())?;
    serde_json::from_str(&metin).map_err(|e| e.to_string())
}

/// Python: _guvenli_zip_yolu. Mutlak yol, surucu harfi ve `..` parcasi reddedilir.
fn guvenli_zip_yolu(ad: &str) -> bool {
    let n = ad.replace('\\', "/");
    if n.starts_with('/')
        || ad.len() >= 2 && ad.as_bytes()[1] == b':' && ad.as_bytes()[0].is_ascii_alphabetic()
    {
        return false;
    }
    !n.split('/').any(|p| p == "..")
}

/// Python: hazir() — yalniz tam dogrulanmis, degismemis, daha yeni paket uygulanabilir.
pub fn hazir(data: &Path) -> bool {
    let klasor = data.join("guncelleme");
    let kayit: Json = afudm_db::kaydet::read_json_or_default(&klasor.join("hazir.json"));
    let Some(surum) = kayit["surum"].as_str().and_then(parcala) else {
        return false;
    };
    if Some(surum) <= parcala(MEVCUT_SURUM) {
        return false;
    }
    let Some(dosyalar) = kayit["dosyalar"].as_object() else {
        return false;
    };
    if !dosyalar.contains_key("AfuDM.exe") {
        return false;
    }
    let beklenen: Option<BTreeMap<String, String>> = dosyalar
        .iter()
        .map(|(k, v)| v.as_str().map(|s| (k.clone(), s.to_string())))
        .collect();
    let Some(beklenen) = beklenen else {
        return false;
    };
    match tarama(&klasor.join("yeni").join("AfuDM")) {
        Ok(mevcut) => mevcut == beklenen,
        Err(_) => false,
    }
}

/// Klasordeki (sembolik baglanti haric) dosyalarin goreli yolu -> sha256 haritasi.
fn tarama(kok: &Path) -> std::io::Result<BTreeMap<String, String>> {
    fn gez(kok: &Path, dir: &Path, sonuc: &mut BTreeMap<String, String>) -> std::io::Result<()> {
        for giris in fs::read_dir(dir)? {
            let yol = giris?.path();
            let meta = fs::symlink_metadata(&yol)?;
            if meta.is_symlink() {
                continue;
            }
            if meta.is_dir() {
                gez(kok, &yol, sonuc)?;
            } else if meta.is_file() {
                let rel = yol
                    .strip_prefix(kok)
                    .unwrap_or(&yol)
                    .components()
                    .map(|c| c.as_os_str().to_string_lossy().into_owned())
                    .collect::<Vec<_>>()
                    .join("/");
                sonuc.insert(rel, format!("{:x}", Sha256::digest(fs::read(&yol)?)));
            }
        }
        Ok(())
    }
    let mut sonuc = BTreeMap::new();
    gez(kok, kok, &mut sonuc)?;
    Ok(sonuc)
}

fn ps_q(yol: &Path) -> String {
    let mut sonuc = String::from("'");
    for c in yol.to_string_lossy().chars() {
        sonuc.push(c);
        if matches!(c, '\'' | '\u{2018}' | '\u{2019}' | '\u{201a}' | '\u{201b}') {
            sonuc.push(c);
        }
    }
    sonuc.push('\'');
    sonuc
}

/// Python: _uygulama_betigi. Sablon `uygula.ps1` dosyasindadir; yer tutucular doldurulur.
pub fn uygulama_betigi(base: &Path, data: &Path, pid: u32) -> String {
    let kaynak = data.join("guncelleme").join("yeni").join("AfuDM");
    let yedek = data.join("guncelleme").join("yedek");
    UYGULA_SABLONU
        .replace("__BASE__", &ps_q(base))
        .replace("__SOURCE__", &ps_q(&kaynak))
        .replace("__BACKUP__", &ps_q(&yedek))
        .replace("__PID__", &pid.to_string())
}

/// Python: guncelleme.uygula(son_kontrol). Betigi yazar, son kontrolden sonra PowerShell'i gizli baslatir.
pub fn uygula_paket(
    data: &Path,
    base: &Path,
    paketli: bool,
    son_kontrol: Option<&dyn Fn() -> bool>,
) -> Json {
    if !paketli {
        return json!({"ok": false, "hata": "Güncelleme yalnız paketli sürümde çalışır."});
    }
    if !hazir(data) {
        return json!({"ok": false, "hata": "Güncelleme hazır değil. Yeniden indir."});
    }
    let betik = data.join("guncelleme").join("uygula.ps1");
    let yazildi = fs::create_dir_all(betik.parent().unwrap_or(data)).and_then(|_| {
        let mut icerik = vec![0xEF, 0xBB, 0xBF]; // UTF-8 BOM (Python: utf-8-sig)
        icerik.extend_from_slice(uygulama_betigi(base, data, std::process::id()).as_bytes());
        fs::write(&betik, icerik)
    });
    if yazildi.is_err() {
        return json!({"ok": false, "hata": "Güncelleme başlatılamadı. Lütfen yeniden dene."});
    }
    if son_kontrol.is_some_and(|f| !f()) {
        return json!({"ok": true, "bekle": true});
    }
    let mut komut = std::process::Command::new("powershell");
    komut
        .args([
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
        ])
        .arg(&betik);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        komut.creation_flags(CREATE_NO_WINDOW);
    }
    match komut.spawn() {
        Ok(_) => json!({"ok": true, "kapat": true}),
        Err(_) => json!({"ok": false, "hata": "Güncelleme başlatılamadı. Lütfen yeniden dene."}),
    }
}

/// Uygulamanin guncelleme durumu (Python app.py'deki _guncelleme_* alanlari).
pub struct Guncelleme {
    data: PathBuf,
    base: PathBuf,
    paketli: bool,
    durum: Mutex<Json>,
    isliyor: Mutex<bool>,
    cikiliyor: Mutex<bool>,
}

impl Guncelleme {
    /// `base`: AfuDM.exe'nin klasoru (ApiCtx.app_dir). `data`: ApiCtx.data_dir. `paketli`: paketli exe mi.
    pub fn new(data: PathBuf, base: PathBuf, paketli: bool) -> Self {
        Guncelleme {
            data,
            base,
            paketli,
            durum: Mutex::new(json!({"durum": "hazir", "inen": 0, "toplam": 0})),
            isliyor: Mutex::new(false),
            cikiliyor: Mutex::new(false),
        }
    }

    /// Python: guncelleme_kontrol. Basarili denetimi kontrol.json'a yazar.
    pub fn kontrol_ve_kaydet(&self) -> Json {
        let sonuc = kontrol(VARSAYILAN_API);
        if truthy(&sonuc["ok"]) {
            let kayit = json!({"zaman": simdi(), "bilgi": sonuc});
            let klasor = self.data.join("guncelleme");
            let _ = fs::create_dir_all(&klasor)
                .and_then(|_| fs::write(klasor.join("kontrol.json"), kayit.to_string()));
        }
        sonuc
    }

    /// Python: guncelleme_indir. Arka planda indirir; ilerlemeyi `durum()` ile verir.
    pub fn indir(self: &Arc<Self>, bilgi: Json) -> Json {
        {
            let mut isliyor = self.isliyor.lock().expect("isliyor kilidi");
            if *isliyor {
                return json!({"ok": true, "zaten": true});
            }
            *isliyor = true;
        }
        *self.durum.lock().expect("durum kilidi") =
            json!({"durum": "iniyor", "inen": 0, "toplam": 0});
        let bu = Arc::clone(self);
        std::thread::spawn(move || {
            let ilerleme = |inen: u64, toplam: u64| {
                *bu.durum.lock().expect("durum kilidi") =
                    json!({"durum": "iniyor", "inen": inen, "toplam": toplam});
            };
            let sonuc = indir_ve_dogrula(&bilgi, &bu.data, Some(&ilerleme as &dyn Fn(u64, u64)));
            *bu.durum.lock().expect("durum kilidi") = if truthy(&sonuc["ok"]) {
                json!({"durum": "bitti"})
            } else {
                json!({"durum": "hata", "hata": sonuc["hata"].as_str().unwrap_or("Güncelleme indirilemedi.")})
            };
            *bu.isliyor.lock().expect("isliyor kilidi") = false;
        });
        json!({"ok": true})
    }

    pub fn durum(&self) -> Json {
        self.durum.lock().expect("durum kilidi").clone()
    }

    /// Python: guncelleme_otomatik_ayarla.
    pub fn otomatik_ayarla(&self, store: &dyn Store, aktif: bool) -> Result<Json> {
        store.set("guncelleme_otomatik", json!(aktif))?;
        if aktif {
            let _ = fs::remove_file(self.data.join("guncelleme").join("kontrol.json"));
        }
        Ok(json!({"ok": true}))
    }

    /// Python: guncelleme_son_kontrol. Son denetim sonucu + otomatik/paketli bayraklari.
    pub fn son_kontrol(&self, store: &dyn Store) -> Result<Json> {
        let durum = json!({"aktif": !otomatik_kapali(store), "paketli": self.paketli});
        let sifir = || {
            let mut m = JsonMap::new();
            m.insert("zaman".into(), json!(0));
            m.extend(durum.as_object().cloned().unwrap_or_default());
            Value::Object(m)
        };
        let once: Json = afudm_db::kaydet::read_json_or_default(
            &self.data.join("guncelleme").join("kontrol.json"),
        );
        if once["bilgi"]["mevcut"].as_str() != Some(MEVCUT_SURUM) {
            return Ok(sifir());
        }
        let mut m = once.as_object().cloned().unwrap_or_default();
        m.extend(durum.as_object().cloned().unwrap_or_default());
        Ok(Value::Object(m))
    }

    /// Python: guncelleme_uygula. `snapshot`: yonetici durumu (ManagerApi::snapshot).
    /// `bekleyen_var`: onay bekleyen eklenti/islem var mi (Python: self._bekleyenler.ozet()).
    pub fn uygula(
        &self,
        store: &dyn Store,
        snapshot: &dyn Fn() -> Result<Json>,
        bekleyen_var: bool,
        otomatik: bool,
        zorla: bool,
    ) -> Json {
        let zorla = zorla && !otomatik;
        let mut cikiliyor = self.cikiliyor.lock().expect("cikiliyor kilidi");
        if *cikiliyor {
            return json!({"ok": true, "zaten": true});
        }
        if otomatik && otomatik_kapali(store) {
            return json!({"ok": true, "iptal": true});
        }
        let neden = mesgul_nedeni(snapshot, bekleyen_var, zorla);
        if !neden.is_empty() {
            return json!({"ok": true, "bekle": true, "neden": neden});
        }
        let son = || {
            mesgul_nedeni(snapshot, bekleyen_var, zorla).is_empty()
                && (!otomatik || !otomatik_kapali(store))
        };
        let sonuc = uygula_paket(&self.data, &self.base, self.paketli, Some(&son));
        if truthy(&sonuc["ok"]) && !truthy(&sonuc["bekle"]) {
            *cikiliyor = true;
        }
        sonuc
    }
}

/// Python: _guncelleme_mesgul. "" bos; "aktif" indirme/motor; "bekleyen" onay bekliyor.
pub fn mesgul_nedeni(
    snapshot: &dyn Fn() -> Result<Json>,
    bekleyen_var: bool,
    zorla: bool,
) -> &'static str {
    let Ok(snap) = snapshot() else {
        return "aktif";
    };
    let (Some(aktif_sayi), Some(bekleyen_sayi)) = (
        sayi(&snap["stat"]["numActive"]),
        sayi(&snap["stat"]["numWaiting"]),
    ) else {
        return "aktif";
    };
    let aktif_is = snap["items"].as_array().is_some_and(|items| {
        items.iter().any(|i| {
            matches!(
                i["status"].as_str(),
                Some("active" | "waiting" | "queued" | "seeding")
            )
        })
    });
    if !truthy(&snap["engine_ok"]) || aktif_sayi != 0 || bekleyen_sayi != 0 || aktif_is {
        return "aktif";
    }
    if !zorla && bekleyen_var {
        return "bekleyen";
    }
    ""
}

fn otomatik_kapali(store: &dyn Store) -> bool {
    matches!(
        store.get("guncelleme_otomatik"),
        Ok(Some(Value::Bool(false)))
    )
}

/// Python: int(stat.get(anahtar, 0)); eksik ya da bos alan 0 sayilir.
fn sayi(v: &Json) -> Option<i64> {
    if v.is_null() {
        Some(0)
    } else {
        tam_al(v)
    }
}

fn tam_al(v: &Json) -> Option<i64> {
    match v {
        Value::Null => None,
        Value::Number(n) => n.as_i64(),
        Value::String(s) => s.trim().parse().ok(),
        Value::Bool(b) => Some(i64::from(*b)),
        _ => None,
    }
}

/// Python truthiness: null, false, 0, "", [] ve {} yanlis.
fn truthy(v: &Json) -> bool {
    match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().is_some_and(|f| f != 0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

fn simdi() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::g1::test_sunucu;

    #[test]
    fn omniget_corrupt_update_state_is_quarantined() {
        let d = gecici("omniget-json");
        let folder = d.join("guncelleme");
        fs::create_dir_all(&folder).unwrap();
        fs::write(folder.join("hazir.json"), "broken").unwrap();
        assert!(!hazir(&d));
        assert!(!folder.join("hazir.json").exists());
        fs::write(folder.join("kontrol.json"), "broken").unwrap();
        let g = Guncelleme::new(d.clone(), d.clone(), false);
        let store = afudm_db::SqliteStore::open_in_memory().unwrap();
        assert_eq!(g.son_kontrol(&store).unwrap()["zaman"], 0);
        assert!(!folder.join("kontrol.json").exists());
        assert_eq!(fs::read_dir(&folder).unwrap().count(), 2);
        fs::remove_dir_all(&d).unwrap();
    }

    #[test]
    fn fix8_ps_tum_tirnaklari_kacirir() {
        assert_eq!(
            ps_q(Path::new("a'\u{2018}\u{2019}\u{201a}\u{201b}b")),
            "'a''\u{2018}\u{2018}\u{2019}\u{2019}\u{201a}\u{201a}\u{201b}\u{201b}b'"
        );
    }

    #[test]
    fn fix8_govde_zaman_asimi_sinirli() {
        assert_eq!(
            ajan().config().timeouts().recv_body,
            Some(Duration::from_secs(900))
        );
    }

    #[test]
    fn fix8_beklenen_boyut_asimi_reddedilir() {
        let d = gecici("fix8-boyut");
        let (bayt, sha) = paket_zip();
        let base = test_sunucu::baslat(vec![
            ("/z.zip", bayt),
            (
                "/z.sha256",
                format!("{sha}  AfuDM-v3.0.1-win64.zip").into_bytes(),
            ),
        ]);
        let mut bilgi = yayin_bilgisi(&base, "3.0.1");
        bilgi["zip_size"] = json!(1);
        let sonuc = indir_ve_dogrula_onekli(&bilgi, &d, None, &base);
        assert_eq!(sonuc["ok"], false);
        assert!(!hazir(&d));
    }

    fn gecici(ad: &str) -> PathBuf {
        let d =
            std::env::temp_dir().join(format!("afudm-g1-guncelleme-{ad}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&d);
        fs::create_dir_all(&d).expect("klasor");
        d
    }

    /// AfuDM/AfuDM.exe iceren zip ve sha256 dosyasi uretir.
    fn paket_zip() -> (Vec<u8>, String) {
        let mut tampon = std::io::Cursor::new(Vec::new());
        {
            let mut yazar = zip::ZipWriter::new(&mut tampon);
            let secenek = zip::write::SimpleFileOptions::default();
            yazar.start_file("AfuDM/AfuDM.exe", secenek).expect("exe");
            yazar.write_all(b"MZ-test-exe").expect("yaz");
            yazar
                .start_file("AfuDM/_internal/veri.txt", secenek)
                .expect("veri");
            yazar.write_all(b"veri").expect("yaz");
            yazar.finish().expect("bitir");
        }
        let zip_bytes = tampon.into_inner();
        let sha = format!("{:x}", Sha256::digest(&zip_bytes));
        (zip_bytes, sha)
    }

    fn yayin_bilgisi(base: &str, yeni: &str) -> Json {
        json!({"ok": true, "var": true, "mevcut": MEVCUT_SURUM, "yeni": yeni,
            "notlar": "", "zip_url": format!("{base}/z.zip"), "sha_url": format!("{base}/z.sha256")})
    }

    #[test]
    fn parcala_surum_karsilastirir() {
        assert_eq!(parcala("v3.0.1"), Some(vec![3, 0, 1]));
        assert_eq!(parcala(" 2.9.6 "), Some(vec![2, 9, 6]));
        assert_eq!(parcala("abc"), None);
        assert_eq!(parcala(""), None);
        assert!(parcala("3.0.10") > parcala("3.0.9"));
    }

    #[test]
    fn kontrol_verisinden_yeni_surum_bulur() {
        let veri = json!({
            "tag_name": "v3.0.1", "body": "notlar",
            "assets": [
                {"name": "AfuDM-v3.0.1-win64.zip", "browser_download_url": format!("{IZINLI_ONEK}v3.0.1/AfuDM-v3.0.1-win64.zip")},
                {"name": "AfuDM-v3.0.1-win64.zip.sha256", "browser_download_url": format!("{IZINLI_ONEK}v3.0.1/AfuDM-v3.0.1-win64.zip.sha256")}
            ]
        });
        let s = kontrol_verisinden(&veri, "3.0.0");
        assert_eq!(s["ok"], true, "{s}");
        assert_eq!(s["var"], true);
        assert_eq!(s["yeni"], "3.0.1");
    }

    #[test]
    fn kontrol_taslak_ve_yabanci_url_reddedilir() {
        let taslak = json!({"tag_name": "v9.0.0", "draft": true});
        assert_eq!(kontrol_verisinden(&taslak, "3.0.0")["var"], false);
        let yabanci = json!({"tag_name": "v3.0.1", "assets": [
            {"name": "AfuDM-v3.0.1-win64.zip", "browser_download_url": "https://evil.example/z.zip"},
            {"name": "AfuDM-v3.0.1-win64.zip.sha256", "browser_download_url": "https://evil.example/z.sha"}]});
        let s = kontrol_verisinden(&yabanci, "3.0.0");
        assert_eq!(s["ok"], false);
        assert_eq!(s["hata"], HATA_KONTROL);
    }

    #[test]
    fn kontrol_ag_hatasinda_turkce_hata() {
        let s = kontrol("http://127.0.0.1:1/yok");
        assert_eq!(s, json!({"ok": false, "hata": HATA_KONTROL}));
    }

    #[test]
    fn indir_dogrula_ve_bekle_dali() {
        let d = gecici("indir");
        let (zip_bytes, sha) = paket_zip();
        let sha_satiri = format!("{sha}  AfuDM-v3.0.1-win64.zip\n");
        let base = test_sunucu::baslat(vec![
            ("/z.zip", zip_bytes.clone()),
            ("/z.sha256", sha_satiri.into_bytes()),
        ]);
        let bilgi = yayin_bilgisi(&base, "3.0.1");
        let s = indir_ve_dogrula_onekli(&bilgi, &d, None, &base);
        assert_eq!(s["ok"], true, "{s}");
        assert!(hazir(&d), "dogrulanmis paket hazir olmali");
        // Paket hazir ama son kontrol 'bekle' diyor: betik yazilir, PowerShell baslamaz.
        let bekle = || false;
        let u = uygula_paket(&d, &d, true, Some(&bekle as &dyn Fn() -> bool));
        assert_eq!(u, json!({"ok": true, "bekle": true}));
        // Paketlenmis degiliz: uygula kayitli degil hatasi verir.
        assert_eq!(uygula_paket(&d, &d, false, None)["ok"], false);
    }

    #[test]
    fn yanlis_sha_reddedilir_ve_zip_silinir() {
        let d = gecici("sha");
        let (zip_bytes, _) = paket_zip();
        let yanlis = format!("{}  AfuDM-v3.0.1-win64.zip\n", "0".repeat(64));
        let base = test_sunucu::baslat(vec![
            ("/z.zip", zip_bytes),
            ("/z.sha256", yanlis.into_bytes()),
        ]);
        let s = indir_ve_dogrula_onekli(&yayin_bilgisi(&base, "3.0.1"), &d, None, &base);
        assert_eq!(
            s,
            json!({"ok": false, "hata": "Güncelleme dosyası doğrulanamadı."})
        );
        assert!(!hazir(&d));
    }

    #[test]
    fn hazir_degisen_dosyada_false_doner() {
        let d = gecici("degisen");
        let (zip_bytes, sha) = paket_zip();
        let base = test_sunucu::baslat(vec![
            ("/z.zip", zip_bytes),
            (
                "/z.sha256",
                format!("{sha}  AfuDM-v3.0.1-win64.zip").into_bytes(),
            ),
        ]);
        assert_eq!(
            indir_ve_dogrula_onekli(&yayin_bilgisi(&base, "3.0.1"), &d, None, &base)["ok"],
            true
        );
        assert!(hazir(&d));
        fs::write(
            d.join("guncelleme")
                .join("yeni")
                .join("AfuDM")
                .join("AfuDM.exe"),
            b"degisti",
        )
        .expect("yaz");
        assert!(!hazir(&d), "degisen paket uygulanmamali");
    }

    #[test]
    fn uygulama_betigi_yer_tutucuları_doldurur() {
        let base = PathBuf::from(r"C:\Users\x'y\AfuDM");
        let data = PathBuf::from(r"C:\Users\x'y\AfuDM\data");
        let betik = uygulama_betigi(&base, &data, 4242);
        assert!(betik.contains("$pidToWait = 4242"));
        assert!(
            betik.contains("'C:\\Users\\x''y\\AfuDM'"),
            "tek tirnak kacisi yok"
        );
        assert!(!betik.contains("__"), "yer tutucu kaldi");
    }

    #[test]
    fn otomatik_ayar_ve_son_kontrol() {
        let d = gecici("otomatik");
        let store = afudm_db::SqliteStore::open_in_memory().expect("db");
        let g = Guncelleme::new(d.clone(), d.clone(), false);
        assert_eq!(g.son_kontrol(&store).expect("son")["aktif"], true);
        g.otomatik_ayarla(&store, false).expect("ayarla");
        assert_eq!(g.son_kontrol(&store).expect("son")["aktif"], false);
        assert_eq!(
            store.get("guncelleme_otomatik").expect("get"),
            Some(json!(false))
        );
    }

    #[test]
    fn uygula_mesgul_ve_paketsiz_dallari() {
        let d = gecici("uygula");
        let store = afudm_db::SqliteStore::open_in_memory().expect("db");
        let g = Guncelleme::new(d.clone(), d.clone(), false);
        let bosta = || {
            Ok(json!({"engine_ok": true, "stat": {"numActive": 0, "numWaiting": 0}, "items": []}))
        };
        let calisan = || Ok(json!({"engine_ok": true, "stat": {"numActive": 1}, "items": []}));
        assert_eq!(mesgul_nedeni(&calisan, false, false), "aktif");
        assert_eq!(mesgul_nedeni(&bosta, true, false), "bekleyen");
        assert_eq!(mesgul_nedeni(&bosta, true, true), "");
        assert_eq!(
            g.uygula(&store, &calisan, false, false, false),
            json!({"ok": true, "bekle": true, "neden": "aktif"})
        );
        // Bosta ama paketli degil: betik calistirilmadan hata doner.
        assert_eq!(
            g.uygula(&store, &bosta, false, false, false),
            json!({"ok": false, "hata": "Güncelleme yalnız paketli sürümde çalışır."})
        );
    }

    #[test]
    fn durum_baslangici_hazir() {
        let g = Guncelleme::new(PathBuf::new(), PathBuf::new(), false);
        assert_eq!(g.durum(), json!({"durum": "hazir", "inen": 0, "toplam": 0}));
    }
}
