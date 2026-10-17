//! Tek bir yt-dlp indirmesi (VideoJob): komut uretimi, surec, cikti pompasi, yedek deneme,
//! birlestirme, iptal ve kayit sekli. Port of video/ytdlp.py VideoJob.
//! Kilit kurali: surec okuma/bekleme sirasinda job kilidi TUTULMAZ; kilit yalniz alan
//! guncellerken alinir (to_dict / iptal bloklanmasin diye).

use super::hata::{kullanici_hata, lang_t};
use super::ilerleme::{
    aria_satiri, hedef_satiri, progress_satiri, yedek_karari, PROGRESS_TAG, PROGRESS_TEMPLATE,
};
use super::mp4mux;
use super::secim::{birlesik_dosya_bul, format_secimi, guvenli_ad};
use afudm_types::{AfuError, Json, Result};
use regex::Regex;
use serde_json::json;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{mpsc, Arc, Mutex, MutexGuard};
use std::thread;
use std::time::{SystemTime, UNIX_EPOCH};

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// Cikti satirlarini isleyen geri cagri (Python on_update). Job kilidi altinda cagrilir.
pub(crate) type Gozlemci = Arc<dyn Fn(&VideoJob) + Send + Sync>;

/// Calisma ortami: yollar ve arac varligi (Python paths + ffmpeg_hazir).
#[derive(Debug, Clone)]
pub(crate) struct Ortam {
    pub ytdlp: String,
    pub ffmpeg: Option<PathBuf>,
    pub aria2c: Option<PathBuf>,
}

#[derive(Debug)]
pub(crate) struct VideoJob {
    pub job_id: String,
    pub url: String,
    pub dest_dir: String,
    pub quality: String,
    pub audio_only: bool,
    pub playlist: bool,
    pub title: String,
    /// active | paused | complete | error | removed
    pub status: String,
    pub error: String,
    /// yt-dlp'nin ham hatasi; `error` ham metni korur (gunluk), kullanici_hata() tek cumle uretir.
    pub ham_hata: String,
    pub downloaded: u64,
    pub total: u64,
    pub speed: u64,
    pub eta: u64,
    pub filename: String,
    /// Hata metinlerinin dili ("auto" | "tr" | "en").
    pub dil: String,
    pub parca_dosyalari: Vec<String>,
    /// Is baslarken ffmpeg var miydi.
    pub ffmpeg_vardi: bool,
    pub cookie_file: String,
    pub user_agent: String,
    /// Sira korunur (Python dict).
    pub headers: Vec<(String, String)>,
    pub proxy: String,
    /// Sayfa basligi; bossa yt-dlp'nin basligi.
    pub dosya_adi: String,
    pub altyazi_diller: String,
    pub oto_altyazi: bool,
    pub altyazi_goem: bool,
    pub kucuk_resim: String,
    pub ustveri_goem: bool,
    pub bolumler: String,
    pub sponsorblock: String,
    pub bolum_araligi: String,
    pub kapsayici: String,
    pub ses_formati: String,
    pub dosya_sablonu: String,
    pub tarayici_cerezi: String,
    pub started_at: f64,
    pub finished_at: f64,
    pub stop: bool,
    /// aria2c dis indirici dusunce yt-dlp'nin kendi indiricisiyle bir kez daha denenir.
    pub yedek_denendi: bool,
    /// 403'te tarayici cerezleri olmadan bir kez daha denenir.
    pub cerezsiz_denendi: bool,
    pub ortam: Ortam,
    /// Calisan yt-dlp surecinin kimligi (0 = yok). Iptal agac olarak bu kimlikle oldurulur.
    pub pid: u32,
}

pub(crate) fn kilitle(job: &Mutex<VideoJob>) -> MutexGuard<'_, VideoJob> {
    job.lock().unwrap_or_else(|p| p.into_inner())
}

fn simdi() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0.0, |d| d.as_secs_f64())
}

fn bildir(g: Option<&Gozlemci>, job: &VideoJob) {
    if let Some(cagri) = g {
        cagri(job);
    }
}

/// Python core/proxy.komut_secenekleri: proxy adresi queue::proxy ile normalize edilip aria2
/// secenekleri olarak doner. Gecersiz adres None (indirici proxysiz calisir, yt-dlp hatayi verir).
fn proxy_ayrimi(url: &str) -> Option<Vec<(String, String)>> {
    let p = crate::queue::proxy::parcala(url).ok()?;
    Some(
        crate::queue::proxy::aria2_secenekleri(&p)
            .into_iter()
            .map(|(anahtar, deger)| (anahtar, deger.as_str().unwrap_or_default().to_string()))
            .collect(),
    )
}

/// Python dayanak: _DEST_RE ile yakalanan parca adinin yalniz dosya adi kismi.
fn ad_parcasi(hedef: &str) -> String {
    Path::new(hedef)
        .file_name()
        .map(|a| a.to_string_lossy().into_owned())
        .unwrap_or_default()
}

impl VideoJob {
    pub(crate) fn yeni(job_id: String, url: String, dest_dir: String, ortam: Ortam) -> Self {
        VideoJob {
            job_id,
            url,
            dest_dir,
            quality: "best".into(),
            audio_only: false,
            playlist: false,
            title: String::new(),
            status: "active".into(),
            error: String::new(),
            ham_hata: String::new(),
            downloaded: 0,
            total: 0,
            speed: 0,
            eta: 0,
            filename: String::new(),
            dil: "auto".into(),
            parca_dosyalari: Vec::new(),
            ffmpeg_vardi: true,
            cookie_file: String::new(),
            user_agent: String::new(),
            headers: Vec::new(),
            proxy: String::new(),
            dosya_adi: String::new(),
            altyazi_diller: String::new(),
            oto_altyazi: false,
            altyazi_goem: false,
            kucuk_resim: String::new(),
            ustveri_goem: false,
            bolumler: String::new(),
            sponsorblock: String::new(),
            bolum_araligi: String::new(),
            kapsayici: String::new(),
            ses_formati: String::new(),
            dosya_sablonu: String::new(),
            tarayici_cerezi: String::new(),
            started_at: simdi(),
            finished_at: 0.0,
            stop: false,
            yedek_denendi: false,
            cerezsiz_denendi: false,
            ortam,
            pid: 0,
        }
    }

    /// Python build_cmd(): yt-dlp argv'si. ffmpeg varligi ortamdan okunur.
    pub(crate) fn komut(&mut self, dis_indirici: bool, cerezsiz: bool) -> Vec<String> {
        let ffmpeg = self.ortam.ffmpeg.clone();
        let ffmpeg_var = ffmpeg.is_some();
        self.ffmpeg_vardi = ffmpeg_var;
        let fmt = format_secimi(&self.quality, self.audio_only, ffmpeg_var);
        let govde = if self.dosya_adi.is_empty() {
            "%(title).150B".to_string()
        } else {
            // Sablonda % ozel: kullanici metnindeki % iki katlanir.
            guvenli_ad(&self.dosya_adi).replace('%', "%%")
        };
        let dest = Path::new(&self.dest_dir);
        let mut out_tpl = dest
            .join(format!("{govde}.%(ext)s"))
            .to_string_lossy()
            .into_owned();
        if self.playlist {
            out_tpl = dest
                .join("%(playlist_title).80B")
                .join("%(playlist_index)03d - %(title).120B.%(ext)s")
                .to_string_lossy()
                .into_owned();
        }
        if !self.dosya_sablonu.is_empty() {
            // Kullanici sablonu HAM gider.
            out_tpl = self.dosya_sablonu.clone();
        }

        let mut cmd: Vec<String> = [
            "--newline",
            "--no-warnings",
            "--encoding",
            "utf-8",
            "--progress",
            "--progress-template",
            PROGRESS_TEMPLATE,
            "--continue",
            "--no-overwrites",
            "--retries",
            "10",
            "--fragment-retries",
            "10",
            "--concurrent-fragments",
            "8",
            "-o",
        ]
        .iter()
        .map(|s| s.to_string())
        .collect();
        cmd.insert(0, self.ortam.ytdlp.clone());
        cmd.push(out_tpl);
        cmd.push("-f".into());
        cmd.push(fmt);

        if let Some(ff) = ffmpeg.as_ref() {
            cmd.push("--ffmpeg-location".into());
            cmd.push(
                ff.parent()
                    .map(|p| p.to_string_lossy().into_owned())
                    .unwrap_or_default(),
            );
            if self.audio_only || self.quality == "audio" {
                let ses = if self.ses_formati.is_empty() {
                    "mp3"
                } else {
                    self.ses_formati.as_str()
                };
                cmd.extend(
                    [
                        "--extract-audio",
                        "--audio-format",
                        ses,
                        "--audio-quality",
                        "0",
                    ]
                    .map(String::from),
                );
            } else {
                let kab = if self.kapsayici.is_empty() {
                    "mp4"
                } else {
                    self.kapsayici.as_str()
                };
                cmd.extend(["--merge-output-format", kab].map(String::from));
            }
        }

        // --- Video Pro bayraklari (bos/kapali ise hicbir sey eklenmez) ---
        if !self.altyazi_diller.is_empty() {
            cmd.extend(["--write-subs", "--sub-langs"].map(String::from));
            cmd.push(self.altyazi_diller.clone());
        }
        if self.oto_altyazi {
            cmd.push("--write-auto-subs".into());
        }
        // --embed-* ffmpeg ister; is basarili kalsin ama kayda not dussun.
        if !ffmpeg_var
            && (self.altyazi_goem
                || self.kucuk_resim == "goem"
                || self.ustveri_goem
                || self.bolumler == "goem")
        {
            self.error = lang_t("note.ffmpegEmbedSkipped", &self.dil);
        }
        if ffmpeg_var && self.altyazi_goem {
            cmd.push("--embed-subs".into());
        }
        if ffmpeg_var && self.kucuk_resim == "goem" {
            cmd.push("--embed-thumbnail".into());
        } else if self.kucuk_resim == "dosya" {
            cmd.push("--write-thumbnail".into());
        }
        if ffmpeg_var && self.ustveri_goem {
            cmd.push("--embed-metadata".into());
        }
        if ffmpeg_var && self.bolumler == "goem" {
            cmd.push("--embed-chapters".into());
        } else if self.bolumler == "ayir" {
            cmd.push("--split-chapters".into());
        }
        if !self.sponsorblock.is_empty() {
            cmd.extend(["--sponsorblock-remove", self.sponsorblock.as_str()].map(String::from));
        }
        if !self.bolum_araligi.is_empty() {
            cmd.push("--download-sections".into());
            cmd.push(format!("*{}", self.bolum_araligi));
        }
        cmd.push(
            if self.playlist {
                "--yes-playlist"
            } else {
                "--no-playlist"
            }
            .into(),
        );

        if !self.cookie_file.is_empty() && !cerezsiz {
            cmd.extend(["--cookies", self.cookie_file.as_str()].map(String::from));
        } else if !self.tarayici_cerezi.is_empty() && !cerezsiz {
            // cookie_file onceliklidir; tarayici cerezi yalniz o bosken gider.
            cmd.extend(["--cookies-from-browser", self.tarayici_cerezi.as_str()].map(String::from));
        }
        if !self.user_agent.is_empty() && !cerezsiz {
            cmd.extend(["--user-agent", self.user_agent.as_str()].map(String::from));
        }
        if !cerezsiz {
            for (anahtar, deger) in &self.headers {
                let kucuk = anahtar.to_lowercase();
                if kucuk == "referer" {
                    cmd.extend(["--referer", deger.as_str()].map(String::from));
                } else if kucuk != "cookie" && kucuk != "user-agent" {
                    cmd.push("--add-header".into());
                    cmd.push(format!("{anahtar}:{deger}"));
                }
            }
        }

        if dis_indirici {
            if let Some(aria) = self.ortam.aria2c.clone() {
                let mut args =
                    "aria2c:-x16 -s16 -k1M --file-allocation=none --console-log-level=error"
                        .to_string();
                // IPv6 yoksa AAAA denemesi indirmeyi iptal eder (Python netcheck.aria2_ipv6_args).
                for bayrak in crate::queue::netcheck::aria2_ipv6_args() {
                    args.push(' ');
                    args.push_str(&bayrak);
                }
                if let Some(secenek) = proxy_ayrimi(&self.proxy) {
                    for (anahtar, deger) in secenek {
                        args.push_str(&format!(" --{anahtar}={deger}"));
                    }
                }
                cmd.push("--downloader".into());
                cmd.push(aria.to_string_lossy().into_owned());
                cmd.push("--downloader-args".into());
                cmd.push(args);
            }
        }
        if !self.proxy.is_empty() {
            cmd.push("--proxy".into());
            cmd.push(self.proxy.clone());
        }
        cmd.push(self.url.clone());
        cmd
    }

    /// Python _birlesik_dosya_kontrol(): eksik parca adi kaldiysa birlesik dosyaya don.
    fn birlesik_dosya_kontrol(&mut self) {
        if let Some(bulunan) = birlesik_dosya_bul(Path::new(&self.dest_dir), &self.filename) {
            let size = std::fs::metadata(&bulunan).map_or(0, |m| m.len());
            self.filename = ad_parcasi(&bulunan.to_string_lossy());
            self.total = size;
            self.downloaded = size;
        }
    }

    /// Python _parse_progress(): AFUDM|done|total|total_est|speed|eta satiri.
    fn ilerleme_uygula(&mut self, satir: &str) {
        if let Some(p) = progress_satiri(satir) {
            self.downloaded = p.indirilen;
            self.total = [p.toplam, p.toplam_tahmini, self.total]
                .into_iter()
                .find(|&v| v != 0)
                .unwrap_or(0);
            self.speed = p.hiz;
            self.eta = p.eta;
        }
    }

    /// Python _hedef_satirini_isle(): hedef dosya adini ve parca listesini guncelle.
    fn hedef_satirini_isle(&mut self, satir: &str) {
        let Some(h) = hedef_satiri(satir) else {
            return;
        };
        self.filename = ad_parcasi(&h.hedef);
        if h.etiket == "download" && !self.parca_dosyalari.contains(&h.hedef) {
            self.parca_dosyalari.push(h.hedef);
        }
    }

    /// Python kullanici_hata(): kullaniciya giden tek cumle.
    pub(crate) fn kullanici_hata(&self) -> String {
        kullanici_hata(&self.ham_hata, &self.error, &self.dil)
    }

    /// Python anlasilir_hata(): ffmpeg eksigi ise not; diger ham metin oldugu gibi doner.
    pub(crate) fn anlasilir_hata(&self, ham: &str) -> String {
        if ham
            .to_lowercase()
            .contains("requested format is not available")
            && !self.ffmpeg_vardi
        {
            let anahtar = if self.audio_only {
                "err.needFfmpegAudio"
            } else {
                "err.needFfmpeg"
            };
            return lang_t(anahtar, &self.dil);
        }
        if !ham.is_empty() {
            log::warn!("yt-dlp hatasi: {ham}");
        }
        ham.to_string()
    }

    /// Python display_title(): dosya adinin govdesi; yoksa baslik; o da yoksa URL.
    pub(crate) fn display_title(&self) -> String {
        if !self.filename.is_empty() {
            if let Some(govde) = Path::new(&self.filename)
                .file_stem()
                .map(|s| s.to_string_lossy().into_owned())
            {
                if !govde.is_empty() {
                    return govde;
                }
            }
        }
        if self.title.is_empty() {
            self.url.clone()
        } else {
            self.title.clone()
        }
    }

    /// Python to_dict(): Afu/aria2 benzeri indirme satiri.
    pub(crate) fn satir(&self) -> Json {
        let total = self.total;
        let done = self.downloaded;
        let elapsed = (simdi() - self.started_at).max(1.0);
        let avg = if done > 0 {
            (done as f64 / elapsed) as u64
        } else {
            0
        };
        json!({
            "gid": self.job_id,
            "kind": "video",
            "status": self.status,
            "title": self.display_title(),
            "filename": self.filename,
            "totalLength": total,
            "completedLength": self.downloaded,
            "downloadSpeed": self.speed,
            "avgSpeed": avg,
            "elapsed": elapsed as i64,
            "remaining": total.saturating_sub(done),
            "uploadSpeed": 0,
            "connections": 0,
            "numSeeders": 0,
            "eta": self.eta,
            "dir": self.dest_dir,
            "errorMessage": self.kullanici_hata(),
            "source": self.url,
        })
    }
}

/// Surec baslatir: penceresiz, stdin kapali, stdout/stderr boru.
fn surec_baslat(args: &[String]) -> std::io::Result<Child> {
    let mut komut = Command::new(&args[0]);
    komut
        .args(&args[1..])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        komut.creation_flags(CREATE_NO_WINDOW);
    }
    komut.spawn()
}

/// Surec agacini oldurur (Python stop(): terminate; burada taskkill /T ile tum alt surecler).
fn surec_agaci_oldur(pid: u32) {
    let mut komut = if cfg!(windows) {
        let mut k = Command::new("taskkill");
        k.args(["/PID", &pid.to_string(), "/T", "/F"]);
        k
    } else {
        let mut k = Command::new("kill");
        k.args(["-9", &pid.to_string()]);
        k
    };
    komut
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        komut.creation_flags(CREATE_NO_WINDOW);
    }
    let _ = komut.status();
}

/// Cikti satirini isle (Python _akisi_oku govdesi). Tail son 30 satiri tutar.
fn satir_isle(job: &Mutex<VideoJob>, ham: &str, g: Option<&Gozlemci>, tail: &mut Vec<String>) {
    let satir = ham.trim();
    if satir.is_empty() {
        return;
    }
    if satir.starts_with(&format!("{PROGRESS_TAG}|")) {
        let mut j = kilitle(job);
        j.ilerleme_uygula(satir);
        bildir(g, &j);
        return;
    }
    if let Some(a) = aria_satiri(satir) {
        let mut j = kilitle(job);
        j.downloaded = a.indirilen;
        if a.toplam > 0 {
            j.total = a.toplam;
        }
        if let Some(h) = a.hiz {
            j.speed = h;
        }
        j.eta = a.eta;
        bildir(g, &j);
        return;
    }
    kilitle(job).hedef_satirini_isle(satir);
    tail.push(satir.to_string());
    if tail.len() > 30 {
        let fazla = tail.len() - 30;
        tail.drain(..fazla);
    }
}

/// Python _akisi_oku(): stdout+stderr'i (yt-dlp ile ayni akis) satir satir okur, bitince kodu doner.
fn akisi_oku(
    job: &Mutex<VideoJob>,
    child: &mut Child,
    g: Option<&Gozlemci>,
) -> (Option<i32>, Vec<String>) {
    let (tx, rx) = mpsc::channel::<Vec<u8>>();
    let mut iplikler = Vec::new();
    if let Some(out) = child.stdout.take() {
        iplikler.push(oku_iplik(out, tx.clone()));
    }
    if let Some(err) = child.stderr.take() {
        iplikler.push(oku_iplik(err, tx.clone()));
    }
    drop(tx);

    let mut tampon: Vec<u8> = Vec::new();
    let mut tail: Vec<String> = Vec::new();
    for parca in rx {
        tampon.extend_from_slice(&parca);
        // aria2c \r ile, yt-dlp \n ile satir sonlandirir: ikisini de sinir say.
        while let Some(konum) = tampon.iter().position(|&b| b == b'\r' || b == b'\n') {
            let satir_bayt: Vec<u8> = tampon.drain(..=konum).collect();
            let satir = String::from_utf8_lossy(&satir_bayt[..satir_bayt.len() - 1]).into_owned();
            satir_isle(job, &satir, g, &mut tail);
        }
    }
    for h in iplikler {
        let _ = h.join();
    }
    let kalan = String::from_utf8_lossy(&tampon).trim().to_string();
    if !kalan.is_empty() {
        if aria_satiri(&kalan).is_none() {
            kilitle(job).hedef_satirini_isle(&kalan);
        }
        tail.push(kalan);
    }
    let kod = child.wait().ok().and_then(|s| s.code());
    (kod, tail)
}

/// Bir boru okuyucusunu ayri is parcacigina alir; parcalar kanala gider.
fn oku_iplik<R: Read + Send + 'static>(
    mut boru: R,
    tx: mpsc::Sender<Vec<u8>>,
) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        let mut tampon = [0u8; 4096];
        loop {
            match boru.read(&mut tampon) {
                Ok(0) | Err(_) => break,
                Ok(n) => {
                    if tx.send(tampon[..n].to_vec()).is_err() {
                        break;
                    }
                }
            }
        }
    })
}

/// Python kendi_birlestir(): ffmpeg yokken iki parcayi kendi MP4 birlestiricimizle tek dosya yapar.
/// Ok(Some(ad)) birlesti; Ok(None) uygulanamadi (parcalar oldugu gibi kalir); Err(neden) hata.
pub(crate) fn kendi_birlestir(parcalar: &[String]) -> std::result::Result<Option<String>, String> {
    if parcalar.len() != 2 {
        return Ok(None);
    }
    let yollar: Vec<PathBuf> = parcalar.iter().map(PathBuf::from).collect();
    if !yollar.iter().all(|y| y.exists()) {
        return Ok(None);
    }
    let mut izler = Vec::new();
    for y in &yollar {
        match mp4mux::izi_oku(y) {
            Ok(iz) => izler.push((y.clone(), iz)),
            Err(_) => return Ok(None), // MP4 ailesinden degil (webm vb.): dokunma
        }
    }
    let video = izler
        .iter()
        .find(|(_, iz)| iz.tur == "vide")
        .map(|(y, _)| y.clone());
    let ses = izler
        .iter()
        .find(|(_, iz)| iz.tur == "soun")
        .map(|(y, _)| y.clone());
    let (Some(video), Some(ses)) = (video, ses) else {
        return Ok(None);
    };

    // "Baslik.f137.mp4" -> "Baslik"
    let stem = video
        .file_stem()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_default();
    let taban = regex_f_son(&stem);
    let aday = |sayi: u32| -> PathBuf {
        let ek = match sayi {
            0 => String::new(),
            1 => " (birlesik)".to_string(),
            n => format!(" (birlesik {n})"),
        };
        video.with_file_name(format!("{taban}{ek}.mp4"))
    };
    // Var olan birlesik cikti EZILMEZ: bos numarali ad ara.
    let mut hedef = aday(0);
    for sayi in 1..1000 {
        if !hedef.exists() && hedef != video && hedef != ses {
            break;
        }
        hedef = aday(sayi);
    }

    // Once gecici dosyaya yaz, sonra atomik olarak tasi: yarim yazmada onceki dosya bozulmaz.
    let on_ek: String = taban.chars().take(40).collect();
    let dizin = hedef.parent().map(Path::to_path_buf).unwrap_or_default();
    let gecici = dizin.join(format!("{on_ek}.{:08x}.yarim", rand::random::<u32>()));
    let sonuc = mp4mux::birlestir(&video, &ses, &gecici, None);
    match sonuc {
        Ok(_) => {}
        Err(e) => {
            let _ = std::fs::remove_file(&gecici);
            return Err(e.to_string().chars().take(160).collect());
        }
    }
    if let Err(e) = std::fs::rename(&gecici, &hedef) {
        let _ = std::fs::remove_file(&gecici);
        return Err(e.to_string().chars().take(160).collect());
    }
    for y in [&video, &ses] {
        let _ = std::fs::remove_file(y);
    }
    Ok(Some(ad_parcasi(&hedef.to_string_lossy())))
}

/// Python re.sub(r"\.f\d+$", "", stem)
fn regex_f_son(stem: &str) -> String {
    static RE: std::sync::OnceLock<Option<Regex>> = std::sync::OnceLock::new();
    match RE.get_or_init(|| Regex::new(r"\.f\d+$").ok()) {
        Some(re) => re.replace(stem, "").into_owned(),
        None => stem.to_string(),
    }
}

/// Bir isi baslatir: cikti pompasi ayri bir is parcacigindadir (Python start()).
pub(crate) fn baslat(job: &Arc<Mutex<VideoJob>>, gozlemci: Option<Gozlemci>) -> Result<()> {
    let args = {
        let mut j = kilitle(job);
        std::fs::create_dir_all(&j.dest_dir)?;
        j.yedek_denendi = false;
        j.cerezsiz_denendi = false;
        j.komut(true, false)
    };
    let child =
        surec_baslat(&args).map_err(|e| AfuError::Engine(format!("yt-dlp baslatilamadi: {e}")))?;
    kilitle(job).pid = child.id();
    let is = Arc::clone(job);
    thread::spawn(move || pump(is, child, gozlemci));
    Ok(())
}

/// Python _pump(): cikti okunur; belli hatalarda (aria2c / cerez 403) bir kez daha denenir.
fn pump(job: Arc<Mutex<VideoJob>>, mut child: Child, gozlemci: Option<Gozlemci>) {
    let g = gozlemci.as_ref();
    loop {
        let (kod, tail) = akisi_oku(&job, &mut child, g);
        {
            let mut j = kilitle(&job);
            if j.stop {
                j.status = "removed".into();
                break;
            }
        }
        if kod == Some(0) {
            let (ffmpeg_yok, parcalar) = {
                let j = kilitle(&job);
                (!j.ffmpeg_vardi, j.parca_dosyalari.clone())
            };
            if ffmpeg_yok {
                // Birlestirme uzun surebilir: kilit tutulmadan yapilir.
                let sonuc = kendi_birlestir(&parcalar);
                let mut j = kilitle(&job);
                match sonuc {
                    Ok(Some(ad)) => {
                        j.filename = ad;
                        bildir(g, &j);
                    }
                    Ok(None) => {}
                    Err(neden) => j.error = format!("birlestirilemedi: {neden}"),
                }
            }
            let mut j = kilitle(&job);
            j.birlesik_dosya_kontrol();
            j.status = "complete".into();
            if j.total > 0 {
                j.downloaded = j.total;
            }
            break;
        }

        // Yalniz BELLI hatalarda tekrarla (Python yedek_karari).
        let yeni_surec = {
            let mut j = kilitle(&job);
            let son = tail.len().saturating_sub(6);
            let karar = yedek_karari(
                &tail[son..].join(" "),
                j.ortam.aria2c.is_some(),
                !j.cookie_file.is_empty() || !j.tarayici_cerezi.is_empty(),
                j.yedek_denendi,
                j.cerezsiz_denendi,
            );
            if karar.is_empty() {
                None
            } else {
                if karar == "aria2c" {
                    j.yedek_denendi = true;
                } else {
                    j.cerezsiz_denendi = true;
                }
                j.downloaded = 0;
                j.speed = 0;
                j.parca_dosyalari.clear();
                let dis_indirici = !j.yedek_denendi;
                let cerezsiz = j.cerezsiz_denendi;
                let args = j.komut(dis_indirici, cerezsiz);
                match surec_baslat(&args) {
                    Ok(c) => {
                        j.pid = c.id();
                        bildir(g, &j);
                        Some(c)
                    }
                    Err(_) => None, // yedek de baslatilamadi: hatayi yaz
                }
            }
        };
        if let Some(c) = yeni_surec {
            child = c;
            continue;
        }

        {
            let mut j = kilitle(&job);
            j.status = "error".into();
            let son = tail.len().saturating_sub(3);
            let birlesik: String = tail[son..].join(" / ").chars().take(500).collect();
            let ham = if birlesik.is_empty() {
                format!("yt-dlp cikis kodu {}", kod.unwrap_or(-1))
            } else {
                birlesik
            };
            j.ham_hata = ham.clone();
            j.error = j.anlasilir_hata(&ham);
        }
        break;
    }
    let mut j = kilitle(&job);
    j.speed = 0;
    j.finished_at = simdi();
    j.pid = 0;
    bildir(g, &j);
}

/// Python stop(): iptal isaretini koyar, surec agacini oldurur. Durum "removed" olur.
pub(crate) fn durdur(job: &Arc<Mutex<VideoJob>>) {
    let pid = {
        let mut j = kilitle(job);
        j.stop = true;
        j.status = "removed".into();
        j.pid
    };
    if pid != 0 {
        surec_agaci_oldur(pid);
    }
}

#[cfg(test)]
mod testler {
    use super::*;
    use std::time::{Duration, Instant};

    fn ortam(ffmpeg: bool) -> Ortam {
        Ortam {
            ytdlp: "yt-dlp".into(),
            ffmpeg: ffmpeg.then(|| PathBuf::from("C:\\afu\\engine\\ffmpeg.exe")),
            aria2c: None,
        }
    }

    fn is(ffmpeg: bool) -> VideoJob {
        VideoJob::yeni(
            "yt:1".into(),
            "https://ornek.test/v".into(),
            "C:\\indir".into(),
            ortam(ffmpeg),
        )
    }

    fn var(komut: &[String], bayrak: &str) -> bool {
        komut.iter().any(|s| s == bayrak)
    }

    #[test]
    fn ffmpeg_varken_birlesik_mp4_ve_ayri_iz_formati() {
        let mut j = is(true);
        j.quality = "720".into();
        let k = j.komut(false, false);
        assert_eq!(k[0], "yt-dlp");
        let f = k.iter().position(|s| s == "-f").expect("-f");
        assert_eq!(
            k[f + 1],
            "bestvideo[height<=720]+bestaudio/best[height<=720]"
        );
        let m = k
            .iter()
            .position(|s| s == "--merge-output-format")
            .expect("birlestirme");
        assert_eq!(k[m + 1], "mp4");
        assert!(var(&k, "--no-playlist"));
        assert_eq!(k.last().map(String::as_str), Some("https://ornek.test/v"));
        assert!(j.ffmpeg_vardi);
    }

    #[test]
    fn ffmpegsiz_kendi_mux_formati_ve_gomme_notu() {
        let mut j = is(false);
        j.altyazi_goem = true;
        let k = j.komut(false, false);
        assert!(!var(&k, "--embed-subs"));
        assert!(!var(&k, "--merge-output-format"));
        assert_eq!(j.error, lang_t("note.ffmpegEmbedSkipped", "auto"));
        assert!(!j.ffmpeg_vardi);
    }

    #[test]
    fn ses_istegi_mp3_ve_playlist_sablonu() {
        let mut j = is(true);
        j.audio_only = true;
        j.playlist = true;
        let k = j.komut(false, false);
        assert!(var(&k, "--extract-audio"));
        assert!(k
            .windows(2)
            .any(|w| w[0] == "--audio-format" && w[1] == "mp3"));
        assert!(var(&k, "--yes-playlist"));
        assert!(k.iter().any(|s| s.contains("%(playlist_index)03d")));
    }

    #[test]
    fn cerez_dosyasi_tarayici_cerezinden_onceliklidir() {
        let mut j = is(true);
        j.cookie_file = "C:\\data\\cerez\\yt_1.txt".into();
        j.tarayici_cerezi = "chrome".into();
        j.user_agent = "UA".into();
        let k = j.komut(false, false);
        assert!(var(&k, "--cookies"));
        assert!(!var(&k, "--cookies-from-browser"));
        assert!(var(&k, "--user-agent"));
        let s = j.komut(false, true);
        assert!(!var(&s, "--cookies"));
        assert!(!var(&s, "--user-agent"));
    }

    #[test]
    fn dosya_adi_yuzde_kacisi() {
        let mut j = is(true);
        j.dosya_adi = "%100 <indirim>".into();
        let k = j.komut(false, false);
        let o = k.iter().position(|s| s == "-o").expect("-o");
        assert!(
            k[o + 1].ends_with("%%100 _indirim_.%(ext)s"),
            "{}",
            k[o + 1]
        );
    }

    #[test]
    fn satir_ve_baslik_kayit_sekli() {
        let mut j = is(true);
        j.filename = "Baslik.mp4".into();
        j.total = 100;
        j.downloaded = 40;
        j.status = "active".into();
        let s = j.satir();
        assert_eq!(s["gid"], json!("yt:1"));
        assert_eq!(s["kind"], json!("video"));
        assert_eq!(s["title"], json!("Baslik"));
        assert_eq!(s["remaining"], json!(60));
        assert_eq!(s["source"], json!("https://ornek.test/v"));
    }

    #[test]
    fn cikti_satirlari_ilerlemeyi_ve_hedefi_gunceller() {
        let job = Mutex::new(is(true));
        let mut tail = Vec::new();
        satir_isle(&job, "AFUDM|50|200|0|1000|3", None, &mut tail);
        satir_isle(
            &job,
            "[#ab 1.0MiB/2.0MiB(50%) CN:4 DL:2.0MiB ETA:5s]",
            None,
            &mut tail,
        );
        satir_isle(
            &job,
            "[download] Destination: C:\\indir\\Baslik.f137.mp4",
            None,
            &mut tail,
        );
        let j = kilitle(&job);
        assert_eq!(j.downloaded, 1024 * 1024);
        assert_eq!(j.total, 2 * 1024 * 1024);
        assert_eq!(j.speed, 2 * 1024 * 1024);
        assert_eq!(j.eta, 5);
        assert_eq!(j.filename, "Baslik.f137.mp4");
        assert_eq!(
            j.parca_dosyalari,
            vec!["C:\\indir\\Baslik.f137.mp4".to_string()]
        );
        assert_eq!(tail.len(), 1, "ilerleme satirlari kuyruga girmez");
    }

    #[test]
    fn birlestirilecek_parca_sayisi_degilse_dokunmaz() {
        assert_eq!(kendi_birlestir(&["tek.mp4".to_string()]), Ok(None));
        assert_eq!(
            kendi_birlestir(&["olmayan-a.mp4".to_string(), "olmayan-b.m4a".to_string()]),
            Ok(None)
        );
    }

    #[test]
    fn proxy_ayrimi_kimlik_ve_adres() {
        let s = proxy_ayrimi("socks5://kul:sif@10.0.0.1:1080").expect("ayrilmali");
        assert!(s.contains(&("all-proxy".into(), "10.0.0.1:1080".into())));
        assert!(s.contains(&("all-proxy-user".into(), "kul".into())));
        assert!(s.contains(&("all-proxy-passwd".into(), "sif".into())));
        assert!(proxy_ayrimi("gecersiz").is_none());
    }

    #[test]
    fn dis_indirici_ipv6_ve_proxy_argumanlari() {
        let mut job = is(false);
        job.ortam.aria2c = Some(std::path::PathBuf::from("C:\\aria2c.exe"));
        job.proxy = "socks5://kul:sif@10.0.0.1:1080".into();
        let komut = job.komut(true, false);
        let konum = komut
            .iter()
            .position(|s| s == "--downloader-args")
            .expect("dis indirici argumanlari olmali");
        let args = &komut[konum + 1];
        assert!(args.starts_with("aria2c:"));
        assert!(args.contains(" --all-proxy=10.0.0.1:1080"));
        let ipv6_var = crate::queue::netcheck::ipv6_usable();
        assert_eq!(args.contains("--disable-ipv6=true"), !ipv6_var);
    }

    /// Gercek yt-dlp + yerel HTTP ile uctan uca indirme. Varsayilan olarak atlanir.
    /// Calistirma (ornek):
    ///   AFU_E2E_YTDLP=<yt-dlp.exe> AFU_E2E_URL=http://127.0.0.1:8765/ornek.mp4 AFU_E2E_DEST=<klasor>
    ///   cargo test -p afudm-core -- --ignored gercek_yt_dlp
    #[test]
    #[ignore]
    fn gercek_yt_dlp_indirme_tamamlanir() {
        let (Ok(ytdlp), Ok(url), Ok(dest)) = (
            std::env::var("AFU_E2E_YTDLP"),
            std::env::var("AFU_E2E_URL"),
            std::env::var("AFU_E2E_DEST"),
        ) else {
            return;
        };
        let ortam = Ortam {
            ytdlp,
            ffmpeg: None,
            aria2c: None,
        };
        let mut j = VideoJob::yeni("yt:e2e".into(), url, dest.clone(), ortam);
        j.dil = "en".into();
        let job = Arc::new(Mutex::new(j));
        let olaylar: Arc<Mutex<Vec<String>>> = Arc::new(Mutex::new(Vec::new()));
        let olay_kaydi = Arc::clone(&olaylar);
        let gozlemci: Gozlemci = Arc::new(move |j: &VideoJob| {
            if let Ok(mut v) = olay_kaydi.lock() {
                v.push(j.status.clone());
            }
        });
        baslat(&job, Some(gozlemci)).expect("baslatilmali");
        let bitis = Instant::now() + Duration::from_secs(120);
        loop {
            let durum = kilitle(&job).status.clone();
            if durum != "active" {
                break;
            }
            assert!(Instant::now() < bitis, "indirme 120 sn icinde bitmedi");
            thread::sleep(Duration::from_millis(100));
        }
        let j = kilitle(&job);
        assert_eq!(
            j.status, "complete",
            "ham hata: {} / hata: {}",
            j.ham_hata, j.error
        );
        assert!(j.total > 0, "toplam boyut bilinmeli");
        assert!(j.filename.ends_with(".mp4"), "dosya adi: {}", j.filename);
        assert!(
            Path::new(&dest).join(&j.filename).is_file(),
            "dosya diskte olmali"
        );
        assert!(olaylar
            .lock()
            .map(|v| v.iter().any(|s| s == "complete"))
            .unwrap_or(false));
    }

    #[test]
    fn durdur_isareti_ve_durum() {
        let job = Arc::new(Mutex::new(is(true)));
        durdur(&job);
        let j = kilitle(&job);
        assert!(j.stop);
        assert_eq!(j.status, "removed");
    }
}
