//! core/eklenti.py EklentiServisi karsiligi: kur, guncelle, geri al, kaldir, etkinlestir,
//! yeniden baslat, ayar, liste, gunluk, islem izleme.
//!
//! EKSIK (SONUC'ta): Python eklenti surecini (EklentiHost) bu surumde calistirmaz.
//! Eklenti kurulabilir, guncellenebilir ve ayarlanabilir; etkinlestirme ise
//! "calistirma yok" hatasiyla BASLAMADI doner. Gunluk ve canli durum bos kalir.

use super::eklenti::{
    ayarlari_dogrula, ayarlari_tasi, hata_yaniti, kopyala_dizin, ozet_dogrula, paket_ac,
    paket_incele, sil, surum_uyumlu, varsayilan_ayarlar, EklentiHatasi, BILINEN_IZINLER,
    MANIFEST_ADI, SURUM,
};
use super::py::{py_float_of, py_int, py_str, truthy};
use afudm_types::{AfuError, Json, JsonMap, Result, Store};
use serde_json::json;
use std::collections::{BTreeSet, HashMap};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, MutexGuard};
use std::time::{SystemTime, UNIX_EPOCH};

const CALISTIRMA_YOK: &str = "Eklenti calistirma bu surumde henuz yok (Python yorumlayici gerekir). Eklenti kurulabilir ama etkinlestirilemez.";

fn simdi() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn kilit<T>(m: &Mutex<T>) -> MutexGuard<'_, T> {
    m.lock().unwrap_or_else(|e| e.into_inner())
}

fn nesne(v: Json) -> JsonMap {
    match v {
        Json::Object(m) => m,
        _ => JsonMap::new(),
    }
}

fn afu_hatasi(e: AfuError) -> EklentiHatasi {
    EklentiHatasi::new("DB_HATASI", e.to_string())
}

/// Python `kayit.get(k) or varsayilan`.
fn veya(kayit: &Json, anahtar: &str, varsayilan: Json) -> Json {
    match kayit.get(anahtar) {
        Some(v) if truthy(v) => v.clone(),
        _ => varsayilan,
    }
}

/// Eklenti sureci bu surumde yok; yalniz durum ve son hata tutulur (Python: EklentiHost).
#[derive(Debug, Clone, Default)]
pub struct EklentiHost {
    pub durum: String,
    pub son_hata: String,
}

impl EklentiHost {
    fn yeni() -> Self {
        Self {
            durum: "kapali".into(),
            son_hata: String::new(),
        }
    }

    /// Python `EklentiHost.baslat` karsiligi: calistirma ortami olmadigi icin her zaman basarisiz.
    pub fn baslat(&mut self) -> Json {
        self.durum = "hata".into();
        self.son_hata = CALISTIRMA_YOK.into();
        json!({"ok": false, "error": CALISTIRMA_YOK, "durum": self.durum})
    }

    pub fn durdur(&mut self) {
        self.durum = "kapali".into();
    }
}

/// Canli islem (kur/guncelle/kaldir/geri al). Python: Islem.
pub struct Islem {
    tur: String,
    ad: String,
    iptal: AtomicBool,
    durum: Mutex<IslemDurum>,
}

#[derive(Clone)]
struct IslemDurum {
    durum: String,
    adim: String,
    mesaj: String,
    hata_kodu: String,
    baslangic: f64,
    bitis: f64,
}

impl Islem {
    fn yeni(tur: &str, ad: &str) -> Self {
        Self {
            tur: tur.into(),
            ad: ad.into(),
            iptal: AtomicBool::new(false),
            durum: Mutex::new(IslemDurum {
                durum: "calisiyor".into(),
                adim: "hazirlaniyor".into(),
                mesaj: String::new(),
                hata_kodu: String::new(),
                baslangic: simdi(),
                bitis: 0.0,
            }),
        }
    }

    fn adim(&self, adim: &str) {
        kilit(&self.durum).adim = adim.into();
    }

    fn calisiyor(&self) -> bool {
        kilit(&self.durum).durum == "calisiyor"
    }

    fn iptal_istendi(&self) -> bool {
        self.iptal.load(Ordering::SeqCst)
    }

    fn ozet(&self) -> Json {
        let d = kilit(&self.durum).clone();
        json!({
            "tur": self.tur, "ad": self.ad, "durum": d.durum, "adim": d.adim,
            "mesaj": d.mesaj, "hata_kodu": d.hata_kodu,
            "baslangic": d.baslangic, "bitis": d.bitis,
            "iptal_edilebilir": d.durum == "calisiyor",
        })
    }
}

/// Eklenti servisi. Klonlanabilir: arka plan is parcacigi ayni durumu paylasir.
#[derive(Clone)]
pub struct EklentiServisi {
    store: Arc<dyn Store>,
    kok: PathBuf,
    yedek_kok: PathBuf,
    hostlar: Arc<Mutex<HashMap<String, EklentiHost>>>,
    islem: Arc<Mutex<Option<Arc<Islem>>>>,
}

impl EklentiServisi {
    /// `app_dir/plugins` (Python: paths.PLUGINS) ve `data_dir/eklenti_yedek` (paths.PLUGIN_YEDEK).
    /// Klasor olusturma hatasi yutulur (Python: mkdir); kurulum sirasinda ayrica hata verir.
    pub fn new(store: Arc<dyn Store>, app_dir: &Path, data_dir: &Path) -> Self {
        let kok = app_dir.join("plugins");
        let _ = std::fs::create_dir_all(&kok);
        Self {
            store,
            kok,
            yedek_kok: data_dir.join("eklenti_yedek"),
            hostlar: Arc::new(Mutex::new(HashMap::new())),
            islem: Arc::new(Mutex::new(None)),
        }
    }

    /// Python `EklentiServisi.kapat`: tum hostlari durdurur.
    pub fn kapat(&self) {
        for host in kilit(&self.hostlar).values_mut() {
            host.durdur();
        }
    }

    fn ayar_i64(&self, anahtar: &str, varsayilan: i64) -> Result<i64> {
        match self.store.get(anahtar)? {
            Some(v) => py_int(&v),
            None => Ok(varsayilan),
        }
    }

    /// Python: int(store.get("eklenti_max_boyut_mb", 200)), float(store.get("eklenti_max_oran", 100.0)).
    fn paket_ayarlari(&self) -> Result<(i64, f64)> {
        let boyut = self.ayar_i64("eklenti_max_boyut_mb", 200)?;
        let oran = match self.store.get("eklenti_max_oran")? {
            Some(v) => py_float_of(&v)
                .ok_or_else(|| AfuError::Invalid("eklenti_max_oran sayi olmali".into()))?,
            None => 100.0,
        };
        Ok((boyut, oran))
    }

    fn imzasiz_izin(&self) -> Result<bool> {
        Ok(match self.store.get("eklenti_imzasiz_izin")? {
            Some(v) => truthy(&v),
            None => true,
        })
    }

    fn host_kaydet(&self, ad: &str) {
        kilit(&self.hostlar)
            .entry(ad.to_string())
            .or_insert_with(EklentiHost::yeni);
    }

    fn islem_basla(&self, tur: &str, ad: &str) -> std::result::Result<Arc<Islem>, EklentiHatasi> {
        let mut g = kilit(&self.islem);
        if g.as_ref().is_some_and(|i| i.calisiyor()) {
            return Err(EklentiHatasi::new(
                "ISLEM_MESGUL",
                "baska bir eklenti islemi suruyor",
            ));
        }
        let yeni = Arc::new(Islem::yeni(tur, ad));
        *g = Some(yeni.clone());
        Ok(yeni)
    }

    /// Python `_arka_planda`: isi thread'de calistirir; `islem` durumunu gunceller.
    fn arka_planda<F>(&self, islem: Arc<Islem>, is_parcasi: F) -> Json
    where
        F: FnOnce(&EklentiServisi, &Islem) -> std::result::Result<String, EklentiHatasi>
            + Send
            + 'static,
    {
        let servis = self.clone();
        let ozet_ilk = islem.ozet();
        std::thread::spawn(move || {
            let sonuc = is_parcasi(&servis, &islem);
            let mut d = kilit(&islem.durum);
            match sonuc {
                Ok(mesaj) => {
                    // Is zaten "bitti" adimina geldiyse gec gelen iptal yok sayilir.
                    if islem.iptal_istendi() && d.durum == "calisiyor" && d.adim != "bitti" {
                        d.durum = "iptal".into();
                        d.mesaj = "islem iptal edildi".into();
                    } else if d.durum == "calisiyor" {
                        d.durum = "bitti".into();
                        d.mesaj = mesaj;
                    }
                }
                Err(e) => {
                    d.durum = "hata".into();
                    d.hata_kodu = e.kod;
                    d.mesaj = e.mesaj;
                }
            }
            d.bitis = simdi();
        });
        json!({"ok": true, "islem": ozet_ilk})
    }

    // -- okuma ----------------------------------------------------------------
    /// Python `liste`: kayit defteri + canli durum.
    pub fn liste(&self) -> Result<Json> {
        let mut kayitlar = Vec::new();
        for kayit in self.store.eklenti_listesi()? {
            let ad = kayit["ad"].as_str().unwrap_or("").to_string();
            let manifest = nesne(veya(&kayit, "manifest", json!({})));
            let (durum, host_hata) = match kilit(&self.hostlar).get(&ad) {
                Some(h) => (h.durum.clone(), h.son_hata.clone()),
                None => ("kapali".to_string(), String::new()),
            };
            let son_hata = if host_hata.is_empty() {
                py_str(&veya(&kayit, "son_hata", json!("")))
            } else {
                host_hata
            };
            let min = manifest.get("afudm_min").map(py_str).unwrap_or_default();
            let max = manifest.get("afudm_max").map(py_str).unwrap_or_default();
            kayitlar.push(json!({
                "ad": ad,
                "baslik": veya(&kayit, "baslik", json!(ad)),
                "surum": kayit.get("surum").cloned().unwrap_or(json!("")),
                "onceki_surum": kayit.get("onceki_surum").cloned().unwrap_or(json!("")),
                "kaynak": kayit.get("kaynak").cloned().unwrap_or(json!("")),
                "aciklama": manifest.get("aciklama").cloned().unwrap_or(json!("")),
                "yazar": manifest.get("yazar").cloned().unwrap_or(json!("")),
                "izinler": veya(&kayit, "izinler", json!([])),
                "domainler": veya(&kayit, "domainler", json!([])),
                "ayar_semasi": veya(&Json::Object(manifest.clone()), "ayar_semasi", json!([])),
                "ayarlar": veya(&kayit, "ayarlar", json!({})),
                "etkin": kayit.get("etkin").is_some_and(truthy),
                "uyumlu": surum_uyumlu(&min, &max, None),
                "afudm_min": min,
                "afudm_max": max,
                "kurulum_at": veya(&kayit, "kurulum_at", json!(0)),
                "guncelleme_at": veya(&kayit, "guncelleme_at", json!(0)),
                "son_hata": son_hata,
                "durum": durum,
                "calisiyor": false,
                "pid": 0,
                "baslama_at": 0.0,
            }));
        }
        let islem = kilit(&self.islem).as_ref().map(|i| i.ozet());
        Ok(json!({
            "ok": true,
            "eklentiler": kayitlar,
            "klasor": self.kok.display().to_string(),
            "afudm_surum": SURUM,
            "bilinen_izinler": BILINEN_IZINLER,
            "guven_modeli": "guvenilen_eklenti",
            "islem": islem,
        }))
    }

    /// Python `gunluk`. Eklenti sureci olmadigi icin satirlar her zaman bostur.
    pub fn gunluk(&self, ad: &str) -> Result<Json> {
        let Some(kayit) = self.store.eklenti(ad)? else {
            return Ok(json!({"ok": false, "error": "eklenti kurulu degil", "satirlar": []}));
        };
        let (durum, son_hata) = match kilit(&self.hostlar).get(ad) {
            Some(h) => (h.durum.clone(), h.son_hata.clone()),
            None => (
                "kapali".to_string(),
                py_str(&veya(&kayit, "son_hata", json!(""))),
            ),
        };
        Ok(json!({"ok": true, "ad": ad, "satirlar": [], "durum": durum, "son_hata": son_hata}))
    }

    /// Python `incele`: kurulumdan once izinler, domainler ve uyumluluk.
    pub fn incele(&self, yol: &str) -> Result<Json> {
        let (boyut, oran) = self.paket_ayarlari()?;
        let mut manifest = match paket_incele(yol, boyut, oran) {
            Ok(m) => m,
            Err(e) => return Ok(hata_yaniti(&e.kod, &e.mesaj)),
        };
        let ad = manifest["ad"].as_str().unwrap_or("").to_string();
        let mevcut = self.store.eklenti(&ad)?;
        let obj = manifest.as_object_mut().expect("manifest nesne");
        obj.insert("kurulu".into(), json!(mevcut.is_some()));
        obj.insert(
            "kurulu_surum".into(),
            json!(mevcut
                .as_ref()
                .and_then(|m| m["surum"].as_str())
                .unwrap_or("")),
        );
        obj.insert("guncelleme_mi".into(), json!(mevcut.is_some()));
        Ok(json!({"ok": true, "manifest": manifest}))
    }

    /// Python `islem`: son islemin canli durumu.
    pub fn islem(&self) -> Json {
        let ozet = kilit(&self.islem).as_ref().map(|i| i.ozet());
        json!({"ok": true, "islem": ozet})
    }

    /// Python `islem_iptal`.
    pub fn islem_iptal(&self) -> Json {
        match kilit(&self.islem).as_ref() {
            Some(i) if i.calisiyor() => {
                i.iptal.store(true, Ordering::SeqCst);
                json!({"ok": true})
            }
            _ => json!({"ok": false, "error": "iptal edilecek islem yok"}),
        }
    }

    // -- kurulum / guncelleme / kaldirma ---------------------------------------
    /// Python `kur`: yerel `.afup` paketinden kurar. Imza yoktur; guvenilen kaynak sarttir.
    pub fn kur(&self, yol: &str, onaylanan_izinler: Option<&[String]>) -> Result<Json> {
        let (boyut, oran) = self.paket_ayarlari()?;
        let manifest = match paket_incele(yol, boyut, oran) {
            Ok(m) => m,
            Err(e) => return Ok(hata_yaniti(&e.kod, &e.mesaj)),
        };
        let ad = manifest["ad"].as_str().unwrap_or("").to_string();
        if self.store.eklenti(&ad)?.is_some() {
            return Ok(hata_yaniti(
                "ZATEN_KURULU",
                &format!("{ad} zaten kurulu — 'Guncelle' kullan"),
            ));
        }
        if !manifest["uyumlu"].as_bool().unwrap_or(false) {
            return Ok(hata_yaniti(
                "UYUMSUZ",
                &format!("eklenti AfuDM {SURUM} ile uyumlu degil"),
            ));
        }
        let beklenen: BTreeSet<String> = manifest["izinler"]
            .as_array()
            .into_iter()
            .flatten()
            .map(py_str)
            .collect();
        if let Some(onay) = onaylanan_izinler {
            let gelen: BTreeSet<String> = onay.iter().cloned().collect();
            if gelen != beklenen {
                return Ok(hata_yaniti(
                    "IZIN_ONAYI",
                    "izin listesi degismis — kurulum ekranini yeniden ac",
                ));
            }
        }
        let islem = match self.islem_basla("kur", &ad) {
            Ok(i) => i,
            Err(e) => return Ok(hata_yaniti(&e.kod, &e.mesaj)),
        };
        let kaynak = PathBuf::from(yol);
        Ok(self.arka_planda(islem, move |s, i| s.kur_isle(i, &manifest, &kaynak)))
    }

    fn kur_isle(
        &self,
        islem: &Islem,
        manifest: &Json,
        kaynak: &Path,
    ) -> std::result::Result<String, EklentiHatasi> {
        let ad = manifest["ad"].as_str().unwrap_or("").to_string();
        let hedef = self.kok.join(&ad);
        islem.adim("dosyalar_aciliyor");
        if islem.iptal_istendi() {
            return Ok(String::new());
        }
        let imzasiz = self.imzasiz_izin().map_err(afu_hatasi)?;
        let gercek_sha = ozet_dogrula(kaynak, manifest, imzasiz)?;
        sil(&hedef);
        let (boyut, oran) = self.paket_ayarlari().map_err(afu_hatasi)?;
        if let Err(e) = paket_ac(kaynak, &hedef, boyut, oran) {
            sil(&hedef);
            return Err(e);
        }
        if islem.iptal_istendi() {
            sil(&hedef);
            return Ok(String::new());
        }
        let giris = manifest["giris"].as_str().unwrap_or("").to_string();
        if !hedef.join(&giris).is_file() {
            sil(&hedef);
            return Err(EklentiHatasi::new(
                "GIRIS_YOK",
                format!("giris dosyasi pakette yok: {giris}"),
            ));
        }
        islem.adim("kaydediliyor");
        let t = simdi();
        let baslik = manifest["baslik"].as_str().unwrap_or("").to_string();
        let surum = manifest["surum"].as_str().unwrap_or("").to_string();
        self.store
            .eklenti_yaz(&nesne(json!({
                "ad": ad,
                "baslik": baslik,
                "surum": surum,
                "kaynak": kaynak.display().to_string(),
                "giris": giris,
                "manifest": manifest,
                "izinler": manifest["izinler"],
                "domainler": manifest["domainler"],
                "ayarlar": Json::Object(varsayilan_ayarlar(manifest)),
                "etkin": false,
                "son_hata": "",
                "onceki_surum": "",
                "kurulum_at": t,
                "guncelleme_at": t,
                "sha256": gercek_sha,
            })))
            .map_err(afu_hatasi)?;
        islem.adim("bitti");
        Ok(format!("{baslik} {surum} kuruldu (devre disi)"))
    }

    /// Python `guncelle`: basarisizsa onceki surume geri doner.
    pub fn guncelle(&self, ad: &str, yol: &str) -> Result<Json> {
        let Some(eski) = self.store.eklenti(ad)? else {
            return Ok(hata_yaniti("KURULU_DEGIL", "eklenti kurulu degil"));
        };
        let (boyut, oran) = self.paket_ayarlari()?;
        let manifest = match paket_incele(yol, boyut, oran) {
            Ok(m) => m,
            Err(e) => return Ok(hata_yaniti(&e.kod, &e.mesaj)),
        };
        let yeni_ad = manifest["ad"].as_str().unwrap_or("").to_string();
        if yeni_ad != ad {
            return Ok(hata_yaniti(
                "YANLIS_PAKET",
                &format!("paket '{yeni_ad}' icin — '{ad}' bekleniyordu"),
            ));
        }
        if !manifest["uyumlu"].as_bool().unwrap_or(false) {
            return Ok(hata_yaniti(
                "UYUMSUZ",
                &format!("yeni surum AfuDM {SURUM} ile uyumlu degil"),
            ));
        }
        let islem = match self.islem_basla("guncelle", ad) {
            Ok(i) => i,
            Err(e) => return Ok(hata_yaniti(&e.kod, &e.mesaj)),
        };
        let kaynak = PathBuf::from(yol);
        Ok(self.arka_planda(islem, move |s, i| {
            s.guncelle_isle(i, &eski, &manifest, &kaynak)
        }))
    }

    fn guncelle_isle(
        &self,
        islem: &Islem,
        eski: &Json,
        manifest: &Json,
        kaynak: &Path,
    ) -> std::result::Result<String, EklentiHatasi> {
        let ad = eski["ad"].as_str().unwrap_or("").to_string();
        let hedef = self.kok.join(&ad);
        let yedek = self.yedek_kok.join(&ad);
        islem.adim("durduruluyor");
        if let Some(host) = kilit(&self.hostlar).get_mut(&ad) {
            host.durdur();
        }
        // Calisan surec olmadigi icin "calisiyordu" her zaman false.
        islem.adim("yedekleniyor");
        std::fs::create_dir_all(&self.yedek_kok).map_err(|e| {
            EklentiHatasi::new(
                "YEDEK_ALINAMADI",
                kes_hata_n(&format!("yedek alinamadi, guncelleme yapilmadi: {e}"), 300),
            )
        })?;
        sil(&yedek);
        if hedef.exists() {
            kopyala_dizin(&hedef, &yedek).map_err(|e| {
                EklentiHatasi::new(
                    "YEDEK_ALINAMADI",
                    kes_hata_n(&format!("yedek alinamadi, guncelleme yapilmadi: {e}"), 300),
                )
            })?;
        }
        let eski_surum = eski["surum"].as_str().unwrap_or("?").to_string();
        match self.guncelle_govde(islem, eski, manifest, kaynak, &hedef) {
            Ok(()) => {
                islem.adim("bitti");
                Ok(format!(
                    "{} {eski_surum} -> {} guncellendi",
                    manifest["baslik"].as_str().unwrap_or(""),
                    manifest["surum"].as_str().unwrap_or("")
                ))
            }
            Err(e) => {
                islem.adim("geri_aliniyor");
                self.geri_al(&ad, eski, &yedek, &hedef);
                let mesaj = format!("{} — onceki surum ({eski_surum}) geri yuklendi", e.mesaj);
                Err(EklentiHatasi::new(&e.kod, kes_hata(&mesaj)))
            }
        }
    }

    fn guncelle_govde(
        &self,
        islem: &Islem,
        eski: &Json,
        manifest: &Json,
        kaynak: &Path,
        hedef: &Path,
    ) -> std::result::Result<(), EklentiHatasi> {
        if islem.iptal_istendi() {
            return Err(EklentiHatasi::new("IPTAL", "islem iptal edildi"));
        }
        let imzasiz = self.imzasiz_izin().map_err(afu_hatasi)?;
        let gercek_sha = ozet_dogrula(kaynak, manifest, imzasiz)?;
        islem.adim("dosyalar_aciliyor");
        sil(hedef);
        let (boyut, oran) = self.paket_ayarlari().map_err(afu_hatasi)?;
        paket_ac(kaynak, hedef, boyut, oran)?;
        let giris = manifest["giris"].as_str().unwrap_or("").to_string();
        if !hedef.join(&giris).is_file() {
            return Err(EklentiHatasi::new(
                "GIRIS_YOK",
                format!("giris dosyasi pakette yok: {giris}"),
            ));
        }
        islem.adim("kaydediliyor");
        let ayarlar = ayarlari_tasi(&nesne(veya(eski, "ayarlar", json!({}))), manifest);
        let t = simdi();
        self.store
            .eklenti_yaz(&nesne(json!({
                "ad": eski["ad"],
                "baslik": manifest["baslik"],
                "surum": manifest["surum"],
                "kaynak": kaynak.display().to_string(),
                "giris": giris,
                "manifest": manifest,
                "izinler": manifest["izinler"],
                "domainler": manifest["domainler"],
                "ayarlar": Json::Object(ayarlar),
                "etkin": veya(eski, "etkin", json!(false)).as_bool().unwrap_or(false),
                "son_hata": "",
                "onceki_surum": eski["surum"].as_str().unwrap_or(""),
                "kurulum_at": veya(eski, "kurulum_at", json!(t)),
                "guncelleme_at": t,
                "sha256": gercek_sha,
            })))
            .map_err(afu_hatasi)?;
        if eski.get("etkin").is_some_and(truthy) {
            // Eklenti sureci yok: etkin eklenti yeni surumle baslatilamaz -> geri alinir.
            let mut host = EklentiHost::yeni();
            let sonuc = host.baslat();
            if !sonuc["ok"].as_bool().unwrap_or(false) {
                return Err(EklentiHatasi::new(
                    "YENI_SURUM_BASLAMADI",
                    kes_hata_n(
                        &format!("yeni surum baslamadi: {}", py_str(&sonuc["error"])),
                        300,
                    ),
                ));
            }
        }
        Ok(())
    }

    /// Python `_geri_al`: dosyalar + kayit eski haline doner. Basarisizsa son hata yazar.
    fn geri_al(&self, ad: &str, eski: &Json, yedek: &Path, hedef: &Path) {
        let sonuc: std::result::Result<(), AfuError> = (|| {
            if let Some(host) = kilit(&self.hostlar).get_mut(ad) {
                host.durdur();
            }
            sil(hedef);
            if yedek.exists() {
                kopyala_dizin(yedek, hedef)?;
            }
            let mut kayit = nesne(eski.clone());
            kayit.insert("guncelleme_at".into(), json!(simdi()));
            kayit.insert(
                "son_hata".into(),
                json!("guncelleme basarisiz — geri alindi"),
            );
            self.store.eklenti_yaz(&kayit)
        })();
        if sonuc.is_err() {
            let _ = self.store.eklenti_alan_yaz(
                ad,
                &nesne(json!({"son_hata": "guncelleme basarisiz ve geri alma tamamlanamadi"})),
            );
        }
    }

    /// Python `elle_geri_al`. DIKKAT (Python hatasi, bkz. SONUC): yedekten geri kopyalar, sonra
    /// `paket_incele(eklenti.json)` cagirir; bu ".afup" olmadigi icin PAKET_TUR ile durur.
    /// Islem durumu "calisiyor" kalir (Python `_arka_planda` kullanmaz).
    pub fn elle_geri_al(&self, ad: &str) -> Result<Json> {
        let Some(kayit) = self.store.eklenti(ad)? else {
            return Ok(hata_yaniti("KURULU_DEGIL", "eklenti kurulu degil"));
        };
        if !truthy(&veya(&kayit, "onceki_surum", json!(""))) {
            return Ok(hata_yaniti("YEDEK_YOK", "onceki surum kaydi yok"));
        }
        let yedek = self.yedek_kok.join(ad);
        if !yedek.exists() {
            return Ok(hata_yaniti("YEDEK_SILINMIS", "yedek dosyalari bulunamadi"));
        }
        let islem = match self.islem_basla("geri_al", ad) {
            Ok(i) => i,
            Err(e) => return Ok(hata_yaniti(&e.kod, &e.mesaj)),
        };
        let ad_kopya = ad.to_string();
        let kok = self.kok.clone();
        let servis = self.clone();
        let ozet = islem.ozet();
        std::thread::spawn(move || {
            let hedef = kok.join(&ad_kopya);
            islem.adim("geri_aliniyor");
            if let Some(host) = kilit(&servis.hostlar).get_mut(&ad_kopya) {
                host.durdur();
            }
            let hata = (|| -> std::result::Result<(), String> {
                sil(&hedef);
                kopyala_dizin(&yedek, &hedef).map_err(|e| e.to_string())?;
                // Python: eski.update(paket_incele(hedef / MANIFEST_ADI)) — .afup olmadigi icin reddedilir.
                paket_incele(&hedef.join(MANIFEST_ADI).display().to_string(), 200, 100.0)
                    .map(|_| ())
                    .map_err(|e| e.mesaj)
            })();
            if let Err(mesaj) = hata {
                islem.adim("hata");
                kilit(&islem.durum).mesaj = kes_hata(&mesaj);
            }
            kilit(&islem.durum).bitis = simdi();
        });
        Ok(json!({"ok": true, "islem": ozet}))
    }

    /// Python `kaldir`.
    pub fn kaldir(&self, ad: &str) -> Result<Json> {
        if self.store.eklenti(ad)?.is_none() {
            return Ok(hata_yaniti("KURULU_DEGIL", "eklenti kurulu degil"));
        }
        let islem = match self.islem_basla("kaldir", ad) {
            Ok(i) => i,
            Err(e) => return Ok(hata_yaniti(&e.kod, &e.mesaj)),
        };
        let ad_kopya = ad.to_string();
        Ok(self.arka_planda(islem, move |s, i| s.kaldir_isle(i, &ad_kopya)))
    }

    fn kaldir_isle(&self, islem: &Islem, ad: &str) -> std::result::Result<String, EklentiHatasi> {
        islem.adim("durduruluyor");
        kilit(&self.hostlar).remove(ad);
        islem.adim("dosyalar_siliniyor");
        sil(&self.kok.join(ad));
        self.store.eklenti_sil(ad).map_err(afu_hatasi)?;
        islem.adim("bitti");
        Ok(format!("{ad} kaldirildi"))
    }

    // -- etkinlik / ayar ----------------------------------------------------------
    /// Python `etkinlestir`. Calistirma ortami olmadigi icin `acik=true` BASLAMADI doner.
    pub fn etkinlestir(&self, ad: &str, acik: bool) -> Result<Json> {
        let Some(kayit) = self.store.eklenti(ad)? else {
            return Ok(hata_yaniti("KURULU_DEGIL", "eklenti kurulu degil"));
        };
        if acik {
            let manifest = veya(&kayit, "manifest", json!({}));
            let min = manifest.get("afudm_min").map(py_str).unwrap_or_default();
            let max = manifest.get("afudm_max").map(py_str).unwrap_or_default();
            if !surum_uyumlu(&min, &max, None) {
                return Ok(hata_yaniti(
                    "UYUMSUZ",
                    &format!("eklenti AfuDM {SURUM} ile uyumlu degil"),
                ));
            }
            self.host_kaydet(ad);
            let (sonuc, durum, son_hata) = {
                let mut hostlar = kilit(&self.hostlar);
                let host = hostlar.get_mut(ad).expect("host_kaydet ekledi");
                let sonuc = host.baslat();
                (sonuc, host.durum.clone(), host.son_hata.clone())
            };
            let basarili = sonuc["ok"].as_bool().unwrap_or(false);
            self.store
                .eklenti_alan_yaz(ad, &nesne(json!({"etkin": basarili, "son_hata": son_hata})))?;
            if !basarili {
                return Ok(json!({
                    "ok": false,
                    "code": "BASLAMADI",
                    "error": sonuc.get("error").map(py_str).filter(|s| !s.is_empty()).unwrap_or_else(|| "eklenti baslatilamadi".into()),
                }));
            }
            return Ok(json!({"ok": true, "durum": durum}));
        }
        if let Some(host) = kilit(&self.hostlar).get_mut(ad) {
            host.durdur();
        }
        self.store
            .eklenti_alan_yaz(ad, &nesne(json!({"etkin": false})))?;
        Ok(json!({"ok": true, "durum": "kapali"}))
    }

    /// Python `yeniden_baslat`.
    pub fn yeniden_baslat(&self, ad: &str) -> Result<Json> {
        let Some(kayit) = self.store.eklenti(ad)? else {
            return Ok(hata_yaniti("KURULU_DEGIL", "eklenti kurulu degil"));
        };
        if !kayit.get("etkin").is_some_and(truthy) {
            return Ok(hata_yaniti(
                "PASIF",
                "eklenti devre disi — once etkinlestir",
            ));
        }
        self.host_kaydet(ad);
        let (sonuc, son_hata) = {
            let mut hostlar = kilit(&self.hostlar);
            let host = hostlar.get_mut(ad).expect("host_kaydet ekledi");
            host.durdur();
            let sonuc = host.baslat();
            (sonuc, host.son_hata.clone())
        };
        self.store
            .eklenti_alan_yaz(ad, &nesne(json!({"son_hata": son_hata})))?;
        if !sonuc["ok"].as_bool().unwrap_or(false) {
            return Ok(json!({
                "ok": false,
                "code": "BASLAMADI",
                "error": py_str(&sonuc["error"]),
            }));
        }
        Ok(json!({"ok": true, "durum": "hata"}))
    }

    /// Python `ayar_kaydet`: eklentinin kendi ayar semasina gore dogrular ve yazar.
    pub fn ayar_kaydet(&self, ad: &str, ayarlar: &Json) -> Result<Json> {
        let Some(kayit) = self.store.eklenti(ad)? else {
            return Ok(hata_yaniti("KURULU_DEGIL", "eklenti kurulu degil"));
        };
        let sema: Vec<Json> = kayit["manifest"]["ayar_semasi"]
            .as_array()
            .cloned()
            .unwrap_or_default();
        let gelen = nesne(ayarlar.clone());
        let mevcut = nesne(veya(&kayit, "ayarlar", json!({})));
        let temiz = match ayarlari_dogrula(&sema, &gelen, &mevcut) {
            Ok(t) => t,
            Err(e) => return Ok(hata_yaniti(&e.kod, &e.mesaj)),
        };
        self.store
            .eklenti_alan_yaz(ad, &nesne(json!({"ayarlar": Json::Object(temiz.clone())})))?;
        // Calisan surec olmadigi icin canli uygulama yoktur.
        Ok(json!({"ok": true, "ayarlar": temiz, "canli_uygulandi": false}))
    }
}

/// Hata metnini Python'daki `[:n]` kesmesi gibi sinirlar.
fn kes_hata_n(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}

fn kes_hata(s: &str) -> String {
    kes_hata_n(s, 400)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn host_baslatma_bu_surumde_basarisiz() {
        let mut h = EklentiHost::yeni();
        let s = h.baslat();
        assert_eq!(s["ok"], json!(false));
        assert_eq!(h.durum, "hata");
        assert!(!h.son_hata.is_empty());
    }

    #[test]
    fn islem_durumu_ve_iptal_ozeti() {
        let i = Islem::yeni("kur", "test");
        assert!(i.calisiyor());
        i.adim("bitti");
        assert_eq!(i.ozet()["adim"], "bitti");
        assert_eq!(i.ozet()["iptal_edilebilir"], json!(true));
    }
}

#[cfg(test)]
mod entegrasyon {
    use super::*;
    use afudm_db::SqliteStore;
    use std::io::Write;

    fn kurulum() -> (EklentiServisi, PathBuf) {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0);
        let kok =
            std::env::temp_dir().join(format!("afudm-g2-servis-{}-{nanos}", std::process::id()));
        let (app, data) = (kok.join("app"), kok.join("data"));
        std::fs::create_dir_all(&app).expect("app klasoru");
        std::fs::create_dir_all(&data).expect("data klasoru");
        let store: Arc<dyn Store> =
            Arc::new(SqliteStore::open_in_memory().expect("bellek ici depo"));
        (EklentiServisi::new(store, &app, &data), kok)
    }

    fn paket(yol: &Path, ad: &str, sha256: Option<&str>) {
        let mut m = json!({
            "ad": ad, "surum": "1.0.0", "giris": "main.py", "afudm_min": "1.0.0",
            "izinler": ["dosya_oku"], "domainler": ["*.ornek.com"],
            "ayar_semasi": [{"anahtar": "boyut", "tur": "sayi", "varsayilan": 3, "en_az": 1, "en_cok": 9}]
        });
        if let Some(s) = sha256 {
            m["sha256"] = json!(s);
        }
        let file = std::fs::File::create(yol).expect("zip olusmali");
        let mut w = zip::ZipWriter::new(file);
        w.start_file("eklenti.json", zip::write::SimpleFileOptions::default())
            .unwrap();
        w.write_all(&serde_json::to_vec(&m).unwrap()).unwrap();
        w.start_file("main.py", zip::write::SimpleFileOptions::default())
            .unwrap();
        w.write_all(b"print('ok')").unwrap();
        w.finish().unwrap();
    }

    /// Arka plan islemi bitene kadar bekler; son durumu doner.
    fn bekle(s: &EklentiServisi) -> Json {
        for _ in 0..500 {
            let i = s.islem()["islem"].clone();
            if i.is_null() || i["durum"] != "calisiyor" {
                return i;
            }
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        panic!("eklenti islemi zaman asimina ugradi");
    }

    #[test]
    fn kur_listele_ayar_kaldir_akisi() {
        let (s, kok) = kurulum();
        let yol = kok.join("a.afup");
        paket(&yol, "test-a", None);
        let r = s
            .kur(yol.to_str().unwrap(), Some(&["dosya_oku".to_string()]))
            .unwrap();
        assert_eq!(r["ok"], true, "{r}");
        let i = bekle(&s);
        assert_eq!(i["durum"], "bitti", "{i}");

        let liste = s.liste().unwrap();
        assert_eq!(liste["eklentiler"][0]["ad"], "test-a");
        assert_eq!(liste["eklentiler"][0]["etkin"], false);
        assert_eq!(liste["eklentiler"][0]["ayarlar"]["boyut"], 3);

        let ikinci = s.kur(yol.to_str().unwrap(), None).unwrap();
        assert_eq!(ikinci["code"], "ZATEN_KURULU");

        let etkin = s.etkinlestir("test-a", true).unwrap();
        assert_eq!(etkin["code"], "BASLAMADI", "calistirma bu surumde yok");

        let ayar = s.ayar_kaydet("test-a", &json!({"boyut": 5})).unwrap();
        assert_eq!(ayar["ayarlar"]["boyut"], 5);
        let asiri = s.ayar_kaydet("test-a", &json!({"boyut": 99})).unwrap();
        assert_eq!(asiri["code"], "AYAR_ARALIK");
        assert_eq!(
            s.liste().unwrap()["eklentiler"][0]["ayarlar"]["boyut"],
            5,
            "atomik: bozuk ayar yazilmamali"
        );

        let k = s.kaldir("test-a").unwrap();
        assert_eq!(k["ok"], true);
        assert_eq!(bekle(&s)["durum"], "bitti");
        assert!(s.liste().unwrap()["eklentiler"]
            .as_array()
            .unwrap()
            .is_empty());
        let _ = std::fs::remove_dir_all(&kok);
    }

    #[test]
    fn ozet_uyusmazligi_kurulumu_durdurur() {
        let (s, kok) = kurulum();
        let yol = kok.join("b.afup");
        paket(&yol, "test-b", Some(&"0".repeat(64)));
        let r = s.kur(yol.to_str().unwrap(), None).unwrap();
        assert_eq!(r["ok"], true, "{r}");
        let i = bekle(&s);
        assert_eq!(i["durum"], "hata");
        assert_eq!(i["hata_kodu"], "OZET_UYUSMUYOR");
        assert!(s.liste().unwrap()["eklentiler"]
            .as_array()
            .unwrap()
            .is_empty());
        let _ = std::fs::remove_dir_all(&kok);
    }

    #[test]
    fn guncelle_yanlis_paketi_reddeder() {
        let (s, kok) = kurulum();
        let yol = kok.join("c.afup");
        paket(&yol, "test-c", None);
        assert_eq!(s.kur(yol.to_str().unwrap(), None).unwrap()["ok"], true);
        assert_eq!(bekle(&s)["durum"], "bitti");
        let diger = kok.join("d.afup");
        paket(&diger, "baska", None);
        let r = s.guncelle("test-c", diger.to_str().unwrap()).unwrap();
        assert_eq!(r["code"], "YANLIS_PAKET");
        let _ = std::fs::remove_dir_all(&kok);
    }
}
