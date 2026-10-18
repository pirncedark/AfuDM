//! Ekip G1. Python: core/automation.py — indirme sonrasi kalici, idempotent otomasyon worker'i.
//! Adimlar: checksum, extract, move, rename, script, notify, power. Kuyruk Store'da (automation_*).
//! SAPMA (bkz. SONUC_G1): extract yalniz .zip destekler (Python shutil.unpack_archive tar/gz da acar).

use afudm_types::{AfuError, Json, JsonMap, Result, Store, UiBridge};
use md5::Md5;
use serde_json::{json, Value};
use sha1::Sha1;
use sha2::{Digest, Sha256, Sha384, Sha512};
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const KOMUT_ZAMAN_ASIMI: Duration = Duration::from_secs(300);

/// Python: AutomationWorker. Calisan tek bir arka plan iscisi; kuyruk Store'dadir.
#[derive(Clone)]
pub struct Otomasyon {
    store: Arc<dyn Store>,
    ui: Arc<dyn UiBridge>,
    uyandir: Arc<(Mutex<bool>, Condvar)>,
    dur: Arc<AtomicBool>,
}

impl Otomasyon {
    pub fn new(store: Arc<dyn Store>, ui: Arc<dyn UiBridge>) -> Self {
        Otomasyon {
            store,
            ui,
            uyandir: Arc::new((Mutex::new(false), Condvar::new())),
            dur: Arc::new(AtomicBool::new(false)),
        }
    }

    /// Python: AutomationWorker.start — arka plan iscisini baslatir.
    pub fn start(&self) {
        let bu = self.clone();
        std::thread::Builder::new()
            .name("AfuDMAutomation".into())
            .spawn(move || bu.dongu())
            .ok();
    }

    pub fn stop(&self) {
        self.dur.store(true, Ordering::SeqCst);
        self.bildir();
    }

    /// Python: enqueue_download. Indirme tamamlaninca etkin adimlari kuyruga koyar.
    pub fn enqueue_download(&self, gid: &str, row: Option<&Json>) -> Result<()> {
        if !self.dogru("automation_enabled")? {
            return Ok(());
        }
        let Some(row) = row else {
            return Ok(());
        };
        let opts = opts_oku(row);
        let adimlar = self
            .store
            .get("automation_steps")?
            .and_then(|v| v.as_array().cloned())
            .unwrap_or_default();
        let dosya = PathBuf::from(row["dest_dir"].as_str().unwrap_or(""))
            .join(row["filename"].as_str().unwrap_or(""));
        let dosya = if dosya.as_os_str().is_empty() {
            ".".to_string()
        } else {
            dosya.to_string_lossy().into_owned()
        };
        for adim in adimlar.iter().filter_map(Value::as_str) {
            if !self.adim_etkin(adim, &opts)? {
                continue;
            }
            let mut yuk = JsonMap::new();
            yuk.insert("path".into(), json!(dosya));
            yuk.insert(
                "checksum".into(),
                if opts["checksum"].is_null() {
                    json!("")
                } else {
                    opts["checksum"].clone()
                },
            );
            self.store.automation_enqueue(gid, adim, Some(&yuk))?;
        }
        self.bildir();
        Ok(())
    }

    /// Python: retry. Isi yeniden kuyruga alir; guncel satiri doner.
    pub fn retry(&self, job_id: i64) -> Result<Json> {
        self.store.automation_retry(job_id)?;
        self.bildir();
        Ok(self
            .store
            .automation_jobs_by_id(job_id)?
            .unwrap_or(Value::Null))
    }

    /// Python: cancel. Guc adimi iptal edilirse bekleyen kapatmayi da (shutdown /a) iptal eder.
    pub fn cancel(&self, job_id: i64) -> Result<Json> {
        let is = self.store.automation_jobs_by_id(job_id)?;
        self.store.automation_cancel(job_id)?;
        if is.as_ref().and_then(|j| j["action"].as_str()) == Some("power") {
            let mut komut = Command::new("shutdown");
            komut.arg("/a").stdout(Stdio::null()).stderr(Stdio::null());
            #[cfg(windows)]
            {
                use std::os::windows::process::CommandExt;
                komut.creation_flags(CREATE_NO_WINDOW);
            }
            let _ = komut.status();
        }
        Ok(self
            .store
            .automation_jobs_by_id(job_id)?
            .unwrap_or(Value::Null))
    }

    fn dongu(&self) {
        while !self.dur.load(Ordering::SeqCst) {
            match self.store.automation_claim() {
                Ok(Some(job)) => {
                    if let Err(hata) = self.calistir(&job) {
                        let id = job["id"].as_i64().unwrap_or(0);
                        let mesaj: String = hata.to_string().chars().take(300).collect();
                        let mut alanlar = JsonMap::new();
                        alanlar.insert("status".into(), json!("error"));
                        alanlar.insert("error".into(), json!(mesaj));
                        alanlar.insert("finished_at".into(), json!(simdi()));
                        let _ = self.store.automation_update(id, &alanlar);
                    }
                }
                _ => self.bekle(Duration::from_secs(1)),
            }
        }
    }

    fn bekle(&self, sure: Duration) {
        let (kilit, kosul) = &*self.uyandir;
        let mut bayrak = kilit.lock().expect("uyandir kilidi");
        if !*bayrak {
            let (yeni, _) = kosul.wait_timeout(bayrak, sure).expect("uyandir bekleme");
            bayrak = yeni;
        }
        *bayrak = false;
    }

    fn bildir(&self) {
        let (kilit, kosul) = &*self.uyandir;
        *kilit.lock().expect("uyandir kilidi") = true;
        kosul.notify_all();
    }

    fn dogru(&self, anahtar: &str) -> Result<bool> {
        Ok(truthy(&self.store.get(anahtar)?.unwrap_or(Value::Null)))
    }

    fn adim_etkin(&self, adim: &str, opts: &Json) -> Result<bool> {
        Ok(match adim {
            "checksum" => self.dogru("automation_checksum")? && truthy(&opts["checksum"]),
            "extract" => self.dogru("automation_extract")?,
            "move" => self.dogru("automation_move_to")?,
            "rename" => self.dogru("automation_rename_to")?,
            "script" => self.dogru("automation_script")?,
            "notify" => self.dogru("automation_notify")?,
            "power" => matches!(
                self.store
                    .get("automation_power")?
                    .as_ref()
                    .and_then(Value::as_str),
                Some("sleep" | "shutdown")
            ),
            _ => true,
        })
    }

    /// Python: _run. Tamamlanan move/rename yolu sonraki adima aktarilir.
    fn calistir(&self, job: &Json) -> Result<()> {
        if job["status"].as_str() == Some("cancelled") {
            return Ok(());
        }
        let id = job["id"].as_i64().unwrap_or(0);
        let eylem = job["action"].as_str().unwrap_or("").to_string();
        let gid = job["download_gid"].as_str().unwrap_or("").to_string();
        let mut p = payload_oku(job);

        let mut onceki = self.store.automation_jobs(&gid, 100_000)?;
        onceki.sort_by_key(|j| j["id"].as_i64().unwrap_or(0));
        for o in &onceki {
            if o["id"].as_i64().unwrap_or(0) >= id {
                break;
            }
            let yol = o["payload"]["path"].as_str().unwrap_or("");
            if o["status"].as_str() == Some("complete")
                && matches!(o["action"].as_str(), Some("move" | "rename"))
                && !yol.is_empty()
            {
                p.insert("path".into(), json!(yol));
            }
        }

        let yol = PathBuf::from(p.get("path").and_then(Value::as_str).unwrap_or(""));
        self.ilerleme(id, 10)?;
        match eylem.as_str() {
            "checksum" => {
                let spec = p
                    .get("checksum")
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .to_string();
                let (algo, beklenen) = spec.split_once(':').unwrap_or((&spec, ""));
                if beklenen.is_empty() {
                    return Err(AfuError::Invalid(
                        "checksum beklenen değer içermiyor".into(),
                    ));
                }
                let hesap = hesapla(algo, &yol)?;
                if hesap != beklenen.to_ascii_lowercase() {
                    return Err(AfuError::Other("checksum doğrulaması başarısız".into()));
                }
            }
            "extract" => {
                if !yol.exists() {
                    return Err(AfuError::Other("arşiv dosyası bulunamadı".into()));
                }
                arsiv_cikar(&yol)?;
            }
            "move" => {
                let hedef = genislet(&self.metin("automation_move_to")?);
                fs::create_dir_all(&hedef)?;
                let yeni = hedef.join(yol.file_name().unwrap_or_default());
                if mutlak(&yol) != mutlak(&yeni) {
                    tasi(&yol, &yeni)?;
                    p.insert("path".into(), json!(yeni.to_string_lossy()));
                }
            }
            "rename" => {
                let sablon = self.metin("automation_rename_to")?.trim().to_string();
                let stem = yol
                    .file_stem()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_default();
                let ext = yol
                    .extension()
                    .map(|s| format!(".{}", s.to_string_lossy()))
                    .unwrap_or_default();
                let yeni_ad = sablon.replace("{name}", &stem).replace("{ext}", &ext);
                if yeni_ad.is_empty() || yeni_ad.contains(['/', '\\']) {
                    return Err(AfuError::Invalid("Geçersiz yeni ad".into()));
                }
                let yeni = yol.with_file_name(&yeni_ad);
                if yol.exists() && yol != yeni {
                    fs::rename(&yol, &yeni)?;
                    p.insert("path".into(), json!(yeni.to_string_lossy()));
                }
            }
            "script" => {
                let komut = self.metin("automation_script")?.trim().to_string();
                if komut.is_empty() {
                    return Err(AfuError::Other("script komutu ayarlanmamış".into()));
                }
                betik_calistir(&komut, yol.parent().unwrap_or(Path::new(".")))?;
            }
            "notify" => {
                let ad = yol
                    .file_name()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_default();
                self.ui
                    .notify("AfuDM", &format!("AfuDM otomasyon tamamlandı: {ad}"));
            }
            "power" => {
                let tamam = self.guc_adimi(id)?;
                if !tamam {
                    return Ok(());
                }
            }
            _ => {}
        }
        let mut alanlar = JsonMap::new();
        alanlar.insert("payload".into(), json!(Value::Object(p).to_string()));
        alanlar.insert("status".into(), json!("complete"));
        alanlar.insert("progress".into(), json!(100));
        alanlar.insert("finished_at".into(), json!(simdi()));
        self.store.automation_update(id, &alanlar)
    }

    /// Python: power dalinin geri sayimi. `false`: kullanici iptal etti.
    fn guc_adimi(&self, id: i64) -> Result<bool> {
        let saniye = self
            .store
            .get("automation_power_seconds")?
            .as_ref()
            .and_then(tamsayi)
            .unwrap_or(60)
            .max(5);
        self.ilerleme(id, 20)?;
        for kalan in (1..=saniye).rev() {
            match self.store.automation_jobs_by_id(id)? {
                Some(j) if j["status"].as_str() != Some("cancelled") => {}
                _ => return Ok(false),
            }
            let oran = ((saniye - kalan) * 80 / saniye).max(20);
            self.ilerleme(id, oran)?;
            std::thread::sleep(Duration::from_secs(1));
        }
        if self
            .store
            .get("automation_power")?
            .as_ref()
            .and_then(Value::as_str)
            == Some("shutdown")
        {
            let mut komut = Command::new("shutdown");
            komut
                .args(["/s", "/t", "0", "/c", "AfuDM otomasyonu"])
                .stdout(Stdio::null())
                .stderr(Stdio::null());
            #[cfg(windows)]
            {
                use std::os::windows::process::CommandExt;
                komut.creation_flags(CREATE_NO_WINDOW);
            }
            if !komut.status().is_ok_and(|s| s.success()) {
                return Err(AfuError::Other(
                    "Bilgisayar kapatılamadı; izinleri kontrol edip yeniden deneyin.".into(),
                ));
            }
        } else if !uyut() {
            return Err(AfuError::Other(
                "Bilgisayar uyutulamadı; güç ayarlarını kontrol edip yeniden deneyin.".into(),
            ));
        }
        Ok(true)
    }

    fn ilerleme(&self, id: i64, oran: i64) -> Result<()> {
        let mut alanlar = JsonMap::new();
        alanlar.insert("progress".into(), json!(oran));
        self.store.automation_update(id, &alanlar)
    }

    fn metin(&self, anahtar: &str) -> Result<String> {
        Ok(self
            .store
            .get(anahtar)?
            .map(|v| {
                v.as_str()
                    .map(str::to_string)
                    .unwrap_or_else(|| v.to_string())
            })
            .unwrap_or_default())
    }
}

// Windows: powrprof SetSuspendState(hazirda bekletme=false, zorla=false, uyanma_devre_disi=false).
// Python: guc.uyut(). Windows disinda uyku desteklenmez (false).
#[cfg(windows)]
#[link(name = "powrprof")]
extern "system" {
    fn SetSuspendState(hibernate: u8, force_critical: u8, disable_wake: u8) -> u8;
}

pub fn uyut() -> bool {
    #[cfg(windows)]
    {
        // SAFETY: SetSuspendState parametreleri salt bayrak (0/1); bellek erisimi yok.
        unsafe { SetSuspendState(0, 0, 0) != 0 }
    }
    #[cfg(not(windows))]
    {
        false
    }
}

fn hesapla(algo: &str, yol: &Path) -> Result<String> {
    let ad = algo.replace('-', "").to_ascii_lowercase();
    let mut dosya = fs::File::open(yol)?;
    match ad.as_str() {
        "md5" => ozet(Md5::new(), &mut dosya),
        "sha1" => ozet(Sha1::new(), &mut dosya),
        "sha256" => ozet(Sha256::new(), &mut dosya),
        "sha384" => ozet(Sha384::new(), &mut dosya),
        "sha512" => ozet(Sha512::new(), &mut dosya),
        _ => Err(AfuError::Other(format!("unsupported hash type {algo}"))),
    }
}

fn ozet<D: Digest>(mut d: D, dosya: &mut fs::File) -> Result<String> {
    let mut tampon = vec![0u8; 1024 * 1024];
    loop {
        let n = dosya.read(&mut tampon)?;
        if n == 0 {
            break;
        }
        d.update(&tampon[..n]);
    }
    Ok(d.finalize().iter().map(|b| format!("{b:02x}")).collect())
}

/// Python: shutil.unpack_archive — bu surumde yalniz .zip.
fn arsiv_cikar(yol: &Path) -> Result<()> {
    let uzanti = yol
        .extension()
        .map(|s| s.to_string_lossy().to_ascii_lowercase())
        .unwrap_or_default();
    if uzanti != "zip" {
        return Err(AfuError::Other("Desteklenmeyen arşiv biçimi".into()));
    }
    let mut arsiv =
        zip::ZipArchive::new(fs::File::open(yol)?).map_err(|e| AfuError::Other(e.to_string()))?;
    let hedef = yol.with_extension("");
    arsiv
        .extract(&hedef)
        .map_err(|e| AfuError::Other(e.to_string()))
}

fn tasi(kaynak: &Path, hedef: &Path) -> Result<()> {
    if fs::rename(kaynak, hedef).is_ok() {
        return Ok(());
    }
    fs::copy(kaynak, hedef)?;
    fs::remove_file(kaynak)?;
    Ok(())
}

/// Python: shlex.split(komut, posix=False) — tirnaklar korunur, bosluklar ayirir.
fn komut_parcala(s: &str) -> Vec<String> {
    let mut sonuc = Vec::new();
    let mut tampon = String::new();
    let (mut tirnak, mut dolu) = (false, false);
    for c in s.chars() {
        match c {
            '"' => {
                tirnak = !tirnak;
                tampon.push(c);
                dolu = true;
            }
            c if c.is_whitespace() && !tirnak => {
                if dolu {
                    sonuc.push(std::mem::take(&mut tampon));
                    dolu = false;
                }
            }
            c => {
                tampon.push(c);
                dolu = true;
            }
        }
    }
    if dolu {
        sonuc.push(tampon);
    }
    sonuc
}

fn betik_calistir(komut: &str, cwd: &Path) -> Result<()> {
    let parcalar = komut_parcala(komut);
    let Some((program, args)) = parcalar.split_first() else {
        return Err(AfuError::Other("script komutu boş".into()));
    };
    let mut cmd = Command::new(program);
    cmd.args(args)
        .current_dir(cwd)
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let mut cocuk = cmd.spawn()?;
    let bitis = Instant::now() + KOMUT_ZAMAN_ASIMI;
    loop {
        if let Some(durum) = cocuk.try_wait()? {
            if durum.success() {
                return Ok(());
            }
            return Err(AfuError::Other(format!(
                "Komut hata kodu ile bitti: {durum}"
            )));
        }
        if Instant::now() >= bitis {
            let _ = cocuk.kill();
            return Err(AfuError::Other("Komut zaman aşımına uğradı".into()));
        }
        std::thread::sleep(Duration::from_millis(200));
    }
}

/// Python: os.path.expanduser — "~" kullanici profiline cevrilir.
fn genislet(yol: &str) -> PathBuf {
    if let Some(kalan) = yol.strip_prefix('~') {
        if let Ok(profil) = std::env::var("USERPROFILE") {
            return PathBuf::from(format!("{profil}{kalan}"));
        }
    }
    PathBuf::from(yol)
}

fn mutlak(yol: &Path) -> PathBuf {
    yol.canonicalize().unwrap_or_else(|_| yol.to_path_buf())
}

fn opts_oku(row: &Json) -> Json {
    match &row["options"] {
        v @ Value::Object(_) => v.clone(),
        Value::String(s) => serde_json::from_str::<Value>(s)
            .ok()
            .filter(Value::is_object)
            .unwrap_or(json!({})),
        _ => json!({}),
    }
}

fn payload_oku(job: &Json) -> JsonMap {
    match &job["payload"] {
        Value::Object(m) => m.clone(),
        Value::String(s) => serde_json::from_str::<Value>(s)
            .ok()
            .and_then(|v| v.as_object().cloned())
            .unwrap_or_default(),
        _ => JsonMap::new(),
    }
}

fn tamsayi(v: &Json) -> Option<i64> {
    match v {
        Value::Number(n) => n.as_i64().or_else(|| n.as_f64().map(|f| f as i64)),
        Value::String(s) => s.trim().parse().ok(),
        _ => None,
    }
}

/// Python truthiness.
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
    use afudm_types::NoUi;

    fn gecici(ad: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("afudm-g1-oto-{ad}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&d);
        fs::create_dir_all(&d).expect("klasor");
        d
    }

    fn kur(store: Arc<afudm_db::SqliteStore>) -> Otomasyon {
        Otomasyon::new(store, Arc::new(NoUi))
    }

    fn indirme(store: &afudm_db::SqliteStore, d: &Path, gid: &str, ad: &str) -> Json {
        store
            .add(
                "http",
                "https://x/y",
                Some(ad),
                Some(d.to_str().expect("utf8")),
                Some(&JsonMap::from_iter([(
                    "checksum".into(),
                    json!("sha256:00"),
                )])),
                None,
                Some(gid),
            )
            .expect("ekle");
        store.by_gid(gid).expect("sorgu").expect("satir")
    }

    #[test]
    fn komut_parcalama_tirnaklari_korur() {
        assert_eq!(
            komut_parcala(r#"a.exe "bir klasor" x"#),
            vec!["a.exe", r#""bir klasor""#, "x"]
        );
    }

    #[test]
    fn etkin_adimlar_kuyruga_girer() {
        let d = gecici("kuyruk");
        let store = Arc::new(afudm_db::SqliteStore::open_in_memory().expect("db"));
        store.set("automation_enabled", json!(true)).expect("set");
        store
            .set("automation_steps", json!(["checksum", "rename", "move"]))
            .expect("set");
        store.set("automation_checksum", json!(true)).expect("set");
        store
            .set("automation_rename_to", json!("{name}-x{ext}"))
            .expect("set");
        let row = indirme(&store, &d, "oto1", "dosya.bin");
        let o = kur(store.clone());
        o.enqueue_download("oto1", Some(&row)).expect("kuyruk");
        let isler = store.automation_jobs("oto1", 100).expect("isler");
        let eylemler: Vec<&str> = isler.iter().filter_map(|j| j["action"].as_str()).collect();
        assert!(eylemler.contains(&"checksum"));
        assert!(eylemler.contains(&"rename"));
        assert!(
            !eylemler.contains(&"move"),
            "move ayari yok, kuyruga girmemeli"
        );
    }

    #[test]
    fn checksum_dogru_ve_yanlis() {
        let d = gecici("checksum");
        let dosya = d.join("veri.bin");
        fs::write(&dosya, b"merhaba").expect("yaz");
        let hex = format!("{:x}", Sha256::digest(b"merhaba"));
        let store = Arc::new(afudm_db::SqliteStore::open_in_memory().expect("db"));
        let o = kur(store.clone());
        let yuk = |c: &str| {
            JsonMap::from_iter([
                ("path".into(), json!(dosya.to_string_lossy())),
                ("checksum".into(), json!(c)),
            ])
        };
        store
            .automation_enqueue("c1", "checksum", Some(&yuk(&format!("sha256:{hex}"))))
            .expect("ekle");
        let is = store.automation_claim().expect("claim").expect("is");
        o.calistir(&is).expect("dogru checksum");
        assert_eq!(
            store
                .automation_jobs_by_id(is["id"].as_i64().expect("id"))
                .expect("j")
                .expect("satir")["status"],
            "complete"
        );

        store
            .automation_enqueue("c2", "checksum", Some(&yuk("sha256:00")))
            .expect("ekle");
        let is2 = store.automation_claim().expect("claim").expect("is");
        let hata = o.calistir(&is2).expect_err("yanlis checksum");
        assert!(hata.to_string().contains("checksum doğrulaması başarısız"));
    }

    #[test]
    fn rename_ve_move_yolu_gunceller() {
        let d = gecici("rename");
        let dosya = d.join("film.mkv");
        fs::write(&dosya, b"v").expect("yaz");
        let store = Arc::new(afudm_db::SqliteStore::open_in_memory().expect("db"));
        store
            .set("automation_rename_to", json!("{name}-son{ext}"))
            .expect("set");
        let o = kur(store.clone());
        let yuk = JsonMap::from_iter([("path".into(), json!(dosya.to_string_lossy()))]);
        store
            .automation_enqueue("r1", "rename", Some(&yuk))
            .expect("ekle");
        let is = store.automation_claim().expect("claim").expect("is");
        o.calistir(&is).expect("rename");
        let yeni = d.join("film-son.mkv");
        assert!(yeni.is_file(), "yeniden adlandirilmis dosya yok");
        assert!(!dosya.exists());

        let hedef = d.join("hedef");
        store
            .set("automation_move_to", json!(hedef.to_string_lossy()))
            .expect("set");
        store
            .automation_enqueue(
                "r1",
                "move",
                Some(&JsonMap::from_iter([(
                    "path".into(),
                    json!(yeni.to_string_lossy()),
                )])),
            )
            .expect("ekle");
        let is2 = store.automation_claim().expect("claim").expect("is");
        o.calistir(&is2).expect("move");
        assert!(hedef.join("film-son.mkv").is_file());
    }

    #[test]
    fn iptal_ve_yeniden_deneme() {
        let store = Arc::new(afudm_db::SqliteStore::open_in_memory().expect("db"));
        store
            .automation_enqueue("i1", "notify", None)
            .expect("ekle");
        let id = store.automation_jobs("i1", 10).expect("isler")[0]["id"]
            .as_i64()
            .expect("id");
        let o = kur(store.clone());
        assert_eq!(o.cancel(id).expect("iptal")["status"], "cancelled");
        assert_eq!(o.retry(id).expect("tekrar")["status"], "queued");
    }
}
