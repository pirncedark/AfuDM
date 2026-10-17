//! SAHIBI: Ekip D2 (video). Python: core/manager.py video dali (add/_launch_video, _on_video_update,
//! pause/resume/remove/pause_all icindeki yt dallari, _recover_orphan_video_jobs, snapshot satirlari)
//! Ayrica video/ytdlp.py (probe, VideoJob) ve video/mp4mux.py.
//! Alt moduller: secim (format/ad/yol), hata (kullaniciya giden metin), ilerleme (cikti
//! ayristirma), cerez (Netscape cerez dosyasi), is (VideoJob, surec, pompa), mp4mux (MP4
//! birlestirme).
//!
//! Imzalar afudm-types::ManagerApi ile sabit; degistirilmez.

mod cerez;
mod hata;
mod ilerleme;
mod is;
mod mp4mux;
mod secim;

use crate::Manager;
use afudm_types::{AfuError, Json, JsonMap, Result, Store};
use is::{Gozlemci, Ortam, VideoJob};
use serde_json::json;
use std::collections::{HashMap, HashSet};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

/// Ekip D2 calisma durumu (Manager::video_state). Tum video isleri ve yt-dlp kimlik sayaci.
#[derive(Default)]
pub struct State {
    /// `yt:<n>` sayaci; ilk kullanimda store.max_video_seq() ile baslar.
    seq: i64,
    isler: HashMap<String, Arc<Mutex<VideoJob>>>,
    /// Python _known_complete: tamamlanma bildirimi bir kez gider.
    bildirilen: Arc<Mutex<HashSet<String>>>,
    /// Tamamlanan isler (baslik, boyut, gid); queue::snapshot bosaltip tamamlandi zincirini calistirir.
    bitenler: Arc<Mutex<Vec<(String, u64, String)>>>,
}

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// Python ytdlp.probe varsayilan zaman asimi (sn).
const PROBE_ZAMAN_ASIMI: Duration = Duration::from_secs(90);

/// Python paths._bundled_or_system("yt-dlp.exe"): once uygulama klasorundeki engine\yt-dlp.exe,
/// yoksa sistemdeki yt-dlp.
fn ytdlp_yolu(app_dir: &Path) -> String {
    let yerel = app_dir.join("engine").join("yt-dlp.exe");
    if yerel.exists() {
        yerel.display().to_string()
    } else {
        "yt-dlp".to_string()
    }
}

/// Python: `x.get(k)` ile ayni; yoksa null.
fn al(v: &Json, anahtar: &str) -> Json {
    v.get(anahtar).cloned().unwrap_or(Json::Null)
}

/// Python truthiness (null/false/0/""/bos dizi-nesne falsy).
pub(crate) fn dogru_mu(v: &Json) -> bool {
    match v {
        Json::Null => false,
        Json::Bool(b) => *b,
        Json::Number(n) => n.as_f64().is_some_and(|f| f != 0.0),
        Json::String(s) => !s.is_empty(),
        Json::Array(a) => !a.is_empty(),
        Json::Object(o) => !o.is_empty(),
    }
}

/// Python str(): metin ise icerigi, degilse JSON gosterimi.
fn json_metin(v: &Json) -> String {
    v.as_str().map_or_else(|| v.to_string(), str::to_string)
}

/// Python options.get(k, "") — metin; null/yok -> bos.
fn secenek_metni(o: &JsonMap, anahtar: &str) -> String {
    match o.get(anahtar) {
        None | Some(Json::Null) => String::new(),
        Some(v) => json_metin(v),
    }
}

fn secenek_dogru(o: &JsonMap, anahtar: &str) -> bool {
    o.get(anahtar).is_some_and(dogru_mu)
}

/// Python probe_sonucu(): yt-dlp -J ciktisini Afu sekline cevirir.
pub(crate) fn probe_sonucu(url: &str, data: &Json) -> Json {
    let formats: Vec<Json> = data
        .get("formats")
        .and_then(|f| f.as_array())
        .map(|dizi| {
            dizi.iter()
                .map(|fmt| {
                    let filesize = al(fmt, "filesize");
                    let filesize = if dogru_mu(&filesize) {
                        filesize
                    } else {
                        al(fmt, "filesize_approx")
                    };
                    json!({
                        "id": al(fmt, "format_id"),
                        "ext": al(fmt, "ext"),
                        "height": al(fmt, "height"),
                        "width": al(fmt, "width"),
                        "fps": al(fmt, "fps"),
                        "vcodec": al(fmt, "vcodec"),
                        "acodec": al(fmt, "acodec"),
                        "filesize": filesize,
                        "note": al(fmt, "format_note"),
                    })
                })
                .collect()
        })
        .unwrap_or_default();
    let title = al(data, "title");
    let entries = match data.get("entries") {
        Some(e) if dogru_mu(e) => e.as_array().map_or(0, |a| a.len()),
        _ => 0,
    };
    json!({
        "title": if dogru_mu(&title) { title } else { json!(url) },
        "duration": al(data, "duration"),
        "thumbnail": al(data, "thumbnail"),
        "uploader": al(data, "uploader"),
        "is_playlist": data.get("_type").and_then(|t| t.as_str()) == Some("playlist"),
        "entries": entries,
        "formats": formats,
    })
}

/// Surec calistirir; zaman asiminda oldurur. Donen: (cikis kodu, stdout, stderr).
fn surec_calistir(
    yol: &str,
    args: &[&str],
    zaman_asimi: Duration,
) -> Result<(Option<i32>, Vec<u8>, Vec<u8>)> {
    let mut komut = Command::new(yol);
    komut
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        komut.creation_flags(CREATE_NO_WINDOW);
    }
    let mut cocuk = komut.spawn()?;
    let mut out_pipe = cocuk.stdout.take();
    let mut err_pipe = cocuk.stderr.take();
    let out_is = std::thread::spawn(move || {
        let mut b = Vec::new();
        if let Some(p) = out_pipe.as_mut() {
            let _ = p.read_to_end(&mut b);
        }
        b
    });
    let err_is = std::thread::spawn(move || {
        let mut b = Vec::new();
        if let Some(p) = err_pipe.as_mut() {
            let _ = p.read_to_end(&mut b);
        }
        b
    });
    let baslangic = Instant::now();
    let kod = loop {
        if let Some(durum) = cocuk.try_wait()? {
            break durum.code();
        }
        if baslangic.elapsed() >= zaman_asimi {
            let _ = cocuk.kill();
            let _ = cocuk.wait();
            return Err(AfuError::Engine(format!(
                "yt-dlp {} sn icinde yanit vermedi",
                zaman_asimi.as_secs()
            )));
        }
        std::thread::sleep(Duration::from_millis(20));
    };
    let stdout = out_is.join().unwrap_or_default();
    let stderr = err_is.join().unwrap_or_default();
    Ok((kod, stdout, stderr))
}

/// Python probe_video -> ytdlp.probe(url): video bilgisi ve format listesi (indirmeden once).
pub fn probe_video(m: &Manager, url: &str) -> Result<Json> {
    let yol = ytdlp_yolu(&m.app_dir);
    let args = [
        "-J",
        "--no-warnings",
        "--no-playlist",
        // --encoding OLMADAN Turkce harfler '?' olur (Python notu); utf-8 zorunlu.
        "--encoding",
        "utf-8",
        "--flat-playlist",
        url,
    ];
    let (kod, stdout, stderr) = surec_calistir(&yol, &args, PROBE_ZAMAN_ASIMI)?;
    if kod != Some(0) {
        let metin = String::from_utf8_lossy(&stderr);
        let kirpik = metin.trim();
        let mesaj = if kirpik.is_empty() {
            "yt-dlp bilgi alamadi"
        } else {
            kirpik
        };
        return Err(AfuError::Engine(mesaj.chars().take(500).collect()));
    }
    let data: Json = serde_json::from_str(&String::from_utf8_lossy(&stdout))?;
    Ok(probe_sonucu(url, &data))
}

fn ortam(m: &Manager) -> Ortam {
    Ortam {
        ytdlp: ytdlp_yolu(&m.app_dir),
        ffmpeg: secim::ffmpeg_yolu(&m.app_dir),
        aria2c: secim::aria2c_yolu(&m.app_dir),
    }
}

fn kilit_durum(m: &Manager) -> std::sync::MutexGuard<'_, State> {
    m.video_state.lock().unwrap_or_else(|p| p.into_inner())
}

/// Python _on_video_update(): is alanlarini store'a yazar; tamamlanmada bildirim verir.
fn gozlemci(
    m: &Manager,
    bildirilen: Arc<Mutex<HashSet<String>>>,
    bitenler: Arc<Mutex<Vec<(String, u64, String)>>>,
) -> Gozlemci {
    let store: Arc<dyn Store> = Arc::clone(&m.store);
    let veri_dizini: PathBuf = m.data_dir.clone();
    Arc::new(move |job: &VideoJob| {
        let mut alanlar = JsonMap::new();
        alanlar.insert("total_bytes".into(), json!(job.total));
        alanlar.insert("done_bytes".into(), json!(job.downloaded));
        alanlar.insert("status".into(), json!(job.status));
        alanlar.insert("filename".into(), json!(job.filename));
        alanlar.insert("title".into(), json!(job.display_title()));
        if matches!(job.status.as_str(), "complete" | "error" | "removed") {
            // Cerez dosyasi bitince silinir (GUVENLIK).
            cerez::sil(&veri_dizini, &job.job_id);
            let bitis = if job.finished_at > 0.0 {
                job.finished_at
            } else {
                simdi()
            };
            alanlar.insert("finished_at".into(), json!(bitis));
            if !job.error.is_empty() {
                alanlar.insert(
                    "error".into(),
                    json!(job.error.chars().take(500).collect::<String>()),
                );
            }
        }
        let _ = store.update_by_gid(&job.job_id, &alanlar);
        if job.status == "complete" {
            let ilk = bildirilen
                .lock()
                .map(|mut kume| kume.insert(job.job_id.clone()))
                .unwrap_or(false);
            // Python _on_complete zinciri (butunluk, bildirim, kancalar) queue tarafinda kosar.
            if ilk {
                if let Ok(mut kuyruk) = bitenler.lock() {
                    kuyruk.push((job.display_title(), job.total, job.job_id.clone()));
                }
            }
        }
    })
}

fn simdi() -> f64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0.0, |d| d.as_secs_f64())
}

/// Python manager.py _launch_video(): video isini olusturur ve baslatir. Donus: `yt:<n>` kimligi.
pub(crate) fn video_ekle_ic(m: &Manager, req: &JsonMap) -> Result<Json> {
    let opt: JsonMap = req
        .get("options")
        .and_then(Json::as_object)
        .cloned()
        .unwrap_or_default();
    let url = secenek_metni(req, "source");
    let dest_dir = secenek_metni(req, "dest_dir");
    let satir_basligi = secenek_metni(req, "title");
    let cerezler = cerez::temizle(req.get("cookies").unwrap_or(&Json::Null));

    let seq = {
        let mut st = kilit_durum(m);
        if st.seq == 0 {
            st.seq = m.store.max_video_seq()?;
        }
        st.seq += 1;
        st.seq
    };
    let job_id = format!("yt:{seq}");
    let cookie_file = if cerezler.is_empty() {
        String::new()
    } else {
        cerez::dosya_yaz(&m.data_dir, &job_id, &cerezler)?
            .to_string_lossy()
            .into_owned()
    };

    let mut job = VideoJob::yeni(job_id.clone(), url.clone(), dest_dir, ortam(m));
    job.quality = opt
        .get("quality")
        .map_or_else(|| "best".to_string(), json_metin);
    job.audio_only = secenek_dogru(&opt, "audio_only");
    job.playlist = secenek_dogru(&opt, "playlist");
    job.title = if satir_basligi.is_empty() {
        url.clone()
    } else {
        satir_basligi
    };
    job.dil = m
        .store
        .get("language")?
        .map_or_else(|| "auto".to_string(), |v| json_metin(&v));
    job.cookie_file = cookie_file;
    job.user_agent = secenek_metni(&opt, "user_agent");
    job.headers = opt
        .get("headers")
        .and_then(Json::as_object)
        .map(|h| h.iter().map(|(k, v)| (k.clone(), json_metin(v))).collect())
        .unwrap_or_default();
    job.proxy = secenek_metni(&opt, "proxy");
    job.dosya_adi = secenek_metni(&opt, "title");
    job.altyazi_diller = secenek_metni(&opt, "altyazi_diller");
    job.oto_altyazi = secenek_dogru(&opt, "oto_altyazi");
    job.altyazi_goem = secenek_dogru(&opt, "altyazi_goem");
    job.kucuk_resim = secenek_metni(&opt, "kucuk_resim");
    job.ustveri_goem = secenek_dogru(&opt, "ustveri_goem");
    job.bolumler = secenek_metni(&opt, "bolumler");
    job.sponsorblock = secenek_metni(&opt, "sponsorblock");
    job.bolum_araligi = secenek_metni(&opt, "bolum_araligi");
    job.kapsayici = secenek_metni(&opt, "kapsayici");
    job.ses_formati = secenek_metni(&opt, "ses_formati");
    job.dosya_sablonu = secenek_metni(&opt, "dosya_sablonu");
    job.tarayici_cerezi = secenek_metni(&opt, "tarayici_cerezi");

    let is = Arc::new(Mutex::new(job));
    let bildirilen = Arc::clone(&kilit_durum(m).bildirilen);
    let bitenler = Arc::clone(&kilit_durum(m).bitenler);
    kilit_durum(m).isler.insert(job_id.clone(), Arc::clone(&is));
    if let Err(hata) = is::baslat(&is, Some(gozlemci(m, bildirilen, bitenler))) {
        kilit_durum(m).isler.remove(&job_id);
        return Err(hata);
    }
    Ok(Json::String(job_id))
}

/// Python snapshot/video satirlari: kaldirilmamis video islerinin kayit sekli.
pub(crate) fn video_satirlari(m: &Manager) -> Vec<Json> {
    let isler: Vec<Arc<Mutex<VideoJob>>> = kilit_durum(m).isler.values().cloned().collect();
    isler
        .iter()
        .map(|is| is::kilitle(is))
        .filter(|j| j.status != "removed")
        .map(|j| j.satir())
        .collect()
}

fn is_bul(m: &Manager, gid: &str) -> Option<Arc<Mutex<VideoJob>>> {
    kilit_durum(m).isler.get(gid).cloned()
}

/// Python pause() yt dali: isi durdurur, kaydi "paused" yapar. Video kimligi yoksa false.
pub(crate) fn durdur(m: &Manager, gid: &str) -> bool {
    let Some(is) = is_bul(m, gid) else {
        return false;
    };
    is::durdur(&is);
    is::kilitle(&is).status = "paused".into();
    let mut alanlar = JsonMap::new();
    alanlar.insert("status".into(), json!("paused"));
    let _ = m.store.update_by_gid(gid, &alanlar);
    true
}

/// Python pause_all() yt dali: bitmemis video islerini durdurur.
pub(crate) fn tumunu_durdur(m: &Manager) {
    let gidler: Vec<String> = kilit_durum(m).isler.keys().cloned().collect();
    for gid in gidler {
        let bitmis = is_bul(m, &gid).is_some_and(|is| {
            matches!(
                is::kilitle(&is).status.as_str(),
                "complete" | "error" | "removed"
            )
        });
        if !bitmis {
            durdur(m, &gid);
        }
    }
}

/// Python remove() yt dali: isi durdurur ve listeden atar. Silinecek dosya yolunu doner
/// (yalniz dosya adi guvenliyse; yol kacisina karsi kontrol).
pub(crate) fn kaldir(m: &Manager, gid: &str) -> Option<PathBuf> {
    let is = kilit_durum(m).isler.remove(gid)?;
    is::durdur(&is);
    let j = is::kilitle(&is);
    guvenli_hedef(&j)
}

/// Video isinin hedef dosyasi (dest_dir + filename). Ad yol kacisi iceriyorsa None.
fn guvenli_hedef(j: &VideoJob) -> Option<PathBuf> {
    let ad = j.filename.as_str();
    if ad.is_empty() || ad == ".." || ad.contains(['/', '\\']) {
        return None;
    }
    Some(Path::new(&j.dest_dir).join(ad))
}

/// Python pause/resume icin aktif ya da bekleyen video isi var mi (can_release_ui).
pub(crate) fn calisan_veya_bekleyen_var(m: &Manager) -> bool {
    kilit_durum(m)
        .isler
        .values()
        .any(|is| matches!(is::kilitle(is).status.as_str(), "active" | "waiting"))
}

/// Python stop(): aktif video islerinin surecini kapatir (durum alanina dokunmaz).
pub(crate) fn aktif_isleri_kapat(m: &Manager) {
    let isler: Vec<Arc<Mutex<VideoJob>>> = kilit_durum(m).isler.values().cloned().collect();
    for is in isler {
        let durum = is::kilitle(&is).status.clone();
        if durum == "active" {
            is::durdur(&is);
            // is::durdur kaydi "removed" yapar; kapanista kayit durumu korunur (acilista yetim olarak duzelir).
            is::kilitle(&is).status = durum;
        }
    }
}

/// Test icin: sahte bir video isi ekler (yt-dlp calistirmadan).
#[cfg(test)]
pub(crate) fn test_is_ekle(m: &Manager, gid: &str, dest_dir: &str, filename: &str, status: &str) {
    let ortam = is::Ortam {
        ytdlp: "yt-dlp".into(),
        ffmpeg: None,
        aria2c: None,
    };
    let mut job = VideoJob::yeni(
        gid.into(),
        "https://ornek.test/v".into(),
        dest_dir.into(),
        ortam,
    );
    job.filename = filename.into();
    job.status = status.into();
    kilit_durum(m)
        .isler
        .insert(gid.into(), Arc::new(Mutex::new(job)));
}

/// Test icin: tamamlanmis bir video isini kuyruga ekler (gozlemcinin yaptigi gibi).
#[cfg(test)]
pub(crate) fn test_tamamlandi_ekle(m: &Manager, title: &str, size: u64, gid: &str) {
    let kuyruk = Arc::clone(&kilit_durum(m).bitenler);
    kuyruk
        .lock()
        .unwrap()
        .push((title.into(), size, gid.into()));
}

/// Python resolve_item_path() yt dali: video isinin hedef dosya yolu.
pub(crate) fn dosya_yolu(m: &Manager, gid: &str) -> Option<PathBuf> {
    let is = is_bul(m, gid)?;
    let j = is::kilitle(&is);
    guvenli_hedef(&j)
}

/// Bu cagrida biten video isleri (baslik, boyut, gid). Liste bosaltilir.
pub(crate) fn tamamlananlari_al(m: &Manager) -> Vec<(String, u64, String)> {
    let kuyruk = Arc::clone(&kilit_durum(m).bitenler);
    let mut liste = kuyruk.lock().unwrap_or_else(|p| p.into_inner());
    std::mem::take(&mut *liste)
}

/// Python: aktif (status == active) video isi sayisi.
pub(crate) fn aktif_sayisi(m: &Manager) -> usize {
    kilit_durum(m)
        .isler
        .values()
        .filter(|is| is::kilitle(is).status == "active")
        .count()
}

/// Aktif video islerinin toplam anlik hizi (bayt/sn).
pub(crate) fn hiz_toplami(m: &Manager) -> u64 {
    kilit_durum(m)
        .isler
        .values()
        .map(|is| {
            let j = is::kilitle(is);
            if j.status == "active" {
                j.speed
            } else {
                0
            }
        })
        .sum()
}

/// Python _recover_orphan_video_jobs(): onceki oturumdan kalan calismayan video kayitlarini duzeltir.
/// Tamamlanmis kardesi olan (ayni kaynak+klasor ya da ayni baslik+klasor) kayit "removed" olur,
/// digerleri "paused" (kaldigi yerden devam edilebilir). Dosyalara dokunulmaz.
pub(crate) fn yetimleri_duzelt(m: &Manager) -> Result<()> {
    let satirlar = m.store.list(None, 100_000)?;
    let secenek = |row: &Json| -> JsonMap {
        match row.get("options") {
            Some(Json::Object(o)) => o.clone(),
            Some(Json::String(s)) => serde_json::from_str::<JsonMap>(s).unwrap_or_default(),
            _ => JsonMap::new(),
        }
    };
    let metin = |row: &Json, k: &str| row.get(k).and_then(Json::as_str).unwrap_or("").to_string();

    let mut tamamlananlar: HashSet<(String, String)> = HashSet::new();
    let mut tamamlanan_basliklar: HashSet<(String, String)> = HashSet::new();
    for row in satirlar
        .iter()
        .filter(|r| metin(r, "kind") == "video" && metin(r, "status") == "complete")
    {
        let dest = metin(row, "dest_dir");
        tamamlananlar.insert((metin(row, "source"), dest.clone()));
        let baslik = secenek(row)
            .get("title")
            .and_then(Json::as_str)
            .unwrap_or("")
            .to_string();
        if !baslik.is_empty() {
            tamamlanan_basliklar.insert((baslik, dest));
        }
    }
    for row in satirlar.iter().filter(|r| metin(r, "kind") == "video") {
        let durum = metin(row, "status");
        if durum != "active" && durum != "waiting" {
            continue;
        }
        let Some(id) = row.get("id").and_then(Json::as_i64) else {
            continue;
        };
        let dest = metin(row, "dest_dir");
        let baslik = secenek(row)
            .get("title")
            .and_then(Json::as_str)
            .unwrap_or("")
            .to_string();
        let kardes_tamamlandi = tamamlananlar.contains(&(metin(row, "source"), dest.clone()))
            || (!baslik.is_empty() && tamamlanan_basliklar.contains(&(baslik, dest)));
        let yeni = if kardes_tamamlandi {
            "removed"
        } else {
            "paused"
        };
        let mut alanlar = JsonMap::new();
        alanlar.insert("status".into(), json!(yeni));
        m.store.update_by_id(id, &alanlar)?;
    }
    Ok(())
}

/// Python find_duplicate(): bellekteki video is kimlikleri (canli sayilir).
pub(crate) fn gidler(m: &Manager) -> HashSet<String> {
    kilit_durum(m).isler.keys().cloned().collect()
}

#[cfg(test)]
mod testler {
    use super::*;

    #[test]
    fn probe_formatlari_ve_varsayilanlari_cikarir() {
        let data = json!({
            "title": null,
            "duration": 12,
            "_type": "playlist",
            "entries": [1, 2, 3],
            "formats": [
                {"format_id": "137", "ext": "mp4", "height": 1080, "width": 1920,
                 "fps": 30, "vcodec": "avc1", "acodec": "none",
                 "filesize": 0, "filesize_approx": 5000, "format_note": "1080p"}
            ]
        });
        let s = probe_sonucu("https://ornek.test/v", &data);
        assert_eq!(s["title"], json!("https://ornek.test/v"));
        assert_eq!(s["is_playlist"], json!(true));
        assert_eq!(s["entries"], json!(3));
        assert_eq!(s["formats"][0]["filesize"], json!(5000));
        assert_eq!(s["formats"][0]["id"], json!("137"));
    }

    #[test]
    fn entries_yoksa_sifir_ve_playlist_degil() {
        let s = probe_sonucu("u", &json!({"title": "Baslik"}));
        assert_eq!(s["entries"], json!(0));
        assert_eq!(s["is_playlist"], json!(false));
        assert_eq!(s["formats"], json!([]));
        assert_eq!(s["title"], json!("Baslik"));
    }
}
