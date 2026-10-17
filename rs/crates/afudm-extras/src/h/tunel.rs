//! Cloudflare hizli tunel yasam dongusu. Python: core/tunel.py (TunnelManager).
//! Surec baslatma `SurecFabrikasi` arkasindadir; testler sahte surecle calisir (gercek tunel acilmaz).

use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{mpsc, Arc, Mutex, MutexGuard};
use std::thread;
use std::time::{Duration, Instant};

use afudm_types::{AfuError, Result};

/// Python `TunnelManager(timeout=30.0)`.
pub const VARSAYILAN_ZAMAN_ASIMI: Duration = Duration::from_secs(30);

const URL_HATASI: &str = "Cloudflare tunnel 30 saniye icinde internet linki vermedi";
const HIC_BASLAMADI: &str = "Cloudflare tüneli başlatılamadı";

/// Calisan surec. stdout ve stderr okuyucular birlikte URL arar (Python: stderr stdout'a birlesir).
pub trait Surec: Send {
    /// Okuyuculari bir kez verir (stdout, stderr).
    fn okuyucular(&mut self) -> Vec<Box<dyn BufRead + Send>>;
    /// Surec bittiyse true.
    fn bitti_mi(&mut self) -> bool;
    /// Sureci oldurur ve bekler (Python terminate + wait + kill).
    fn sonlandir(&mut self);
}

/// Surec baslatici. Gercek uygulama `GercekFabrika`, testler sahte uygular.
pub trait SurecFabrikasi: Send + Sync {
    fn baslat(&self, program: &Path, args: &[String]) -> std::io::Result<Box<dyn Surec>>;
}

/// Gercek surec (Windows'ta penceresiz: CREATE_NO_WINDOW).
pub struct GercekFabrika;

struct GercekSurec {
    cocuk: Child,
}

impl SurecFabrikasi for GercekFabrika {
    fn baslat(&self, program: &Path, args: &[String]) -> std::io::Result<Box<dyn Surec>> {
        let mut komut = Command::new(program);
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
        let cocuk = komut.spawn()?;
        Ok(Box::new(GercekSurec { cocuk }))
    }
}

impl Surec for GercekSurec {
    fn okuyucular(&mut self) -> Vec<Box<dyn BufRead + Send>> {
        let mut liste: Vec<Box<dyn BufRead + Send>> = Vec::new();
        if let Some(out) = self.cocuk.stdout.take() {
            liste.push(Box::new(BufReader::new(out)));
        }
        if let Some(err) = self.cocuk.stderr.take() {
            liste.push(Box::new(BufReader::new(err)));
        }
        liste
    }

    fn bitti_mi(&mut self) -> bool {
        !matches!(self.cocuk.try_wait(), Ok(None))
    }

    fn sonlandir(&mut self) {
        let _ = self.cocuk.kill();
        let _ = self.cocuk.wait();
    }
}

/// Python `_URL`: `https://[a-z0-9-]+\.trycloudflare\.com` (buyuk/kucuk harf duyarsiz).
/// Eslesen metin ozgun biciminde doner.
pub fn trycloudflare_url_bul(satir: &str) -> Option<String> {
    const ALAN: &str = ".trycloudflare.com";
    let kucuk = satir.to_ascii_lowercase();
    let mut bas = 0;
    while let Some(p) = kucuk[bas..].find("https://") {
        let s = bas + p;
        let host_bas = s + "https://".len();
        let mut e = host_bas;
        while e < kucuk.len() && matches!(kucuk.as_bytes()[e], b'a'..=b'z' | b'0'..=b'9' | b'-') {
            e += 1;
        }
        if e > host_bas && kucuk[e..].starts_with(ALAN) {
            return Some(satir[s..e + ALAN.len()].to_string());
        }
        bas = s + 1;
    }
    None
}

/// Python `_read_url`: surecin ciktisinda URL'yi bekler. Zaman asimi veya surec bitisi None doner.
fn url_bekle(surec: &mut dyn Surec, zaman_asimi: Duration) -> Option<String> {
    let (tx, rx) = mpsc::channel::<String>();
    for okuyucu in surec.okuyucular() {
        let tx = tx.clone();
        thread::spawn(move || {
            for satir in okuyucu.lines() {
                let Ok(satir) = satir else { break };
                if let Some(url) = trycloudflare_url_bul(&satir) {
                    if tx.send(url).is_err() {
                        break;
                    }
                }
            }
        });
    }
    drop(tx);
    let bitis = Instant::now() + zaman_asimi;
    loop {
        let kalan = bitis.saturating_duration_since(Instant::now());
        if kalan.is_zero() {
            return None;
        }
        match rx.recv_timeout(kalan.min(Duration::from_millis(100))) {
            Ok(url) => return Some(url),
            Err(mpsc::RecvTimeoutError::Timeout) => {
                if surec.bitti_mi() {
                    return None;
                }
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => return None,
        }
    }
}

struct Ic {
    fabrika: Arc<dyn SurecFabrikasi>,
    exe: PathBuf,
    zaman_asimi: Duration,
    surec: Option<Box<dyn Surec>>,
    url: String,
    port: u16,
    yeniden_denendi: bool,
    /// Python `_process` kimligi: her basarili baslatma ya da durdurma artirir; eski izleyiciler kendiliginden biter.
    kimlik: u64,
    baslatma_sayisi: u32,
    hata: String,
}

impl Ic {
    /// Python `_start_once`: surec baslatir, URL bekler; basarisizsa surec oldurulur.
    fn bir_kez(&mut self, port: u16) -> Result<String> {
        let args = vec![
            "tunnel".to_string(),
            "--url".to_string(),
            format!("http://127.0.0.1:{port}"),
            "--no-autoupdate".to_string(),
        ];
        let mut surec = self.fabrika.baslat(&self.exe, &args)?;
        self.baslatma_sayisi += 1;
        match url_bekle(surec.as_mut(), self.zaman_asimi) {
            Some(url) => {
                self.surec = Some(surec);
                self.port = port;
                self.url = url.clone();
                self.kimlik += 1;
                Ok(url)
            }
            None => {
                surec.sonlandir();
                Err(AfuError::Engine(URL_HATASI.to_string()))
            }
        }
    }

    /// Python `stop()` icindeki durum sifirlama.
    fn durdur_ic(&mut self) {
        if let Some(mut surec) = self.surec.take() {
            surec.sonlandir();
        }
        self.url.clear();
        self.port = 0;
        self.kimlik += 1;
    }
}

fn kilit(ic: &Mutex<Ic>) -> MutexGuard<'_, Ic> {
    ic.lock().unwrap_or_else(|e| e.into_inner())
}

/// Python `TunnelManager`. Klonlanabilir; tum kopyalar ayni tuneli yonetir.
#[derive(Clone)]
pub struct TunelYoneticisi {
    ic: Arc<Mutex<Ic>>,
}

/// Cloudflare yolu: `afudm_engine::engines::yol(app_dir, "cloudflared")` (paketli ya da sistem).
pub fn cloudflared_yolu(app_dir: &Path) -> Option<PathBuf> {
    afudm_engine::engines::yol(app_dir, "cloudflared")
}

impl TunelYoneticisi {
    pub fn yeni(exe: PathBuf, fabrika: Arc<dyn SurecFabrikasi>, zaman_asimi: Duration) -> Self {
        Self {
            ic: Arc::new(Mutex::new(Ic {
                fabrika,
                exe,
                zaman_asimi,
                surec: None,
                url: String::new(),
                port: 0,
                yeniden_denendi: false,
                kimlik: 0,
                baslatma_sayisi: 0,
                hata: String::new(),
            })),
        }
    }

    /// Gercek cloudflared ile (30 sn zaman asimi).
    pub fn gercek(exe: PathBuf) -> Self {
        Self::yeni(exe, Arc::new(GercekFabrika), VARSAYILAN_ZAMAN_ASIMI)
    }

    /// Python `active`: surec var ve URL bilinir.
    pub fn aktif(&self) -> bool {
        let g = kilit(&self.ic);
        g.surec.is_some() && !g.url.is_empty()
    }

    pub fn url(&self) -> String {
        kilit(&self.ic).url.clone()
    }

    /// Son hata metni (Python `error`); bos ise hata yok.
    pub fn hata(&self) -> String {
        kilit(&self.ic).hata.clone()
    }

    /// Toplam surec baslatma denemesi (Python `launch_count`).
    pub fn baslatma_sayisi(&self) -> u32 {
        kilit(&self.ic).baslatma_sayisi
    }

    /// Python `start(port)`: ayni port aktifse mevcut URL'yi doner; degilse tuneli kurar
    /// (en fazla 2 deneme) ve izleyiciyi baslatir.
    pub fn baslat(&self, port: u16) -> Result<String> {
        let mut g = kilit(&self.ic);
        if g.surec.is_some() && !g.url.is_empty() && g.port == port {
            return Ok(g.url.clone());
        }
        g.durdur_ic();
        g.yeniden_denendi = false;
        g.hata.clear();
        let mut son = HIC_BASLAMADI.to_string();
        for _ in 0..2 {
            match g.bir_kez(port) {
                Ok(url) => {
                    let kimlik = g.kimlik;
                    spawn_izle(Arc::clone(&self.ic), kimlik);
                    return Ok(url);
                }
                Err(e) => son = e.to_string(),
            }
        }
        g.hata = son.clone();
        Err(AfuError::Engine(son))
    }

    /// Python `stop()`: sureci oldurur, URL ve port'u temizler.
    pub fn durdur(&self) {
        kilit(&self.ic).durdur_ic();
    }
}

fn spawn_izle(ic: Arc<Mutex<Ic>>, kimlik: u64) {
    thread::spawn(move || izle(ic, kimlik));
}

/// Python `_watch`: surec cikarsa tek sefer yeniden baslatir; ikinci cikista hata yazar ve biter.
fn izle(ic: Arc<Mutex<Ic>>, kimlik: u64) {
    loop {
        thread::sleep(Duration::from_millis(100));
        let mut g = kilit(&ic);
        if g.kimlik != kimlik {
            return;
        }
        let bitti = match g.surec.as_mut() {
            Some(surec) => surec.bitti_mi(),
            None => return,
        };
        if !bitti {
            continue;
        }
        if g.yeniden_denendi {
            g.hata = "Cloudflare tunnel beklenmedik sekilde kapandi".to_string();
            g.surec = None;
            g.url.clear();
            return;
        }
        g.yeniden_denendi = true;
        let port = g.port;
        g.surec = None;
        g.url.clear();
        match g.bir_kez(port) {
            Ok(_) => {
                let yeni = g.kimlik;
                spawn_izle(Arc::clone(&ic), yeni);
            }
            Err(e) => {
                g.hata = format!("Cloudflare tunnel yeniden baslatilamadi: {e}");
                g.surec = None;
                g.url.clear();
            }
        }
        return;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::VecDeque;
    use std::io::Cursor;
    use std::sync::atomic::{AtomicBool, Ordering};

    struct SahteSurec {
        satirlar: Vec<String>,
        bitti: Arc<AtomicBool>,
    }

    impl Surec for SahteSurec {
        fn okuyucular(&mut self) -> Vec<Box<dyn BufRead + Send>> {
            let govde = self.satirlar.join("\n").into_bytes();
            vec![Box::new(Cursor::new(govde))]
        }
        fn bitti_mi(&mut self) -> bool {
            self.bitti.load(Ordering::SeqCst)
        }
        fn sonlandir(&mut self) {
            self.bitti.store(true, Ordering::SeqCst);
        }
    }

    /// Her baslatmada siradaki senaryoyu verir; args kaydi tutulur.
    struct SahteFabrika {
        senaryolar: Mutex<VecDeque<(Vec<String>, Arc<AtomicBool>)>>,
        argumanlar: Mutex<Vec<Vec<String>>>,
    }

    impl SurecFabrikasi for SahteFabrika {
        fn baslat(&self, _program: &Path, args: &[String]) -> std::io::Result<Box<dyn Surec>> {
            self.argumanlar
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .push(args.to_vec());
            let siradaki = self
                .senaryolar
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .pop_front();
            match siradaki {
                Some((satirlar, bitti)) => Ok(Box::new(SahteSurec { satirlar, bitti })),
                None => Err(std::io::Error::other("senaryo kalmadi")),
            }
        }
    }

    fn fabrika(senaryolar: Vec<(Vec<String>, Arc<AtomicBool>)>) -> Arc<SahteFabrika> {
        Arc::new(SahteFabrika {
            senaryolar: Mutex::new(senaryolar.into_iter().collect()),
            argumanlar: Mutex::new(Vec::new()),
        })
    }

    fn url_satiri(url: &str) -> Vec<String> {
        vec![format!("2026-10-18 INF |  {url}  |")]
    }

    #[test]
    fn url_bulucu_python_gibi() {
        assert_eq!(
            trycloudflare_url_bul("INF | https://ab-12.trycloudflare.com |"),
            Some("https://ab-12.trycloudflare.com".to_string())
        );
        assert_eq!(trycloudflare_url_bul("https://example.com"), None);
        assert_eq!(
            trycloudflare_url_bul("HTTPS://X.TRYCLOUDFLARE.COM"),
            Some("HTTPS://X.TRYCLOUDFLARE.COM".to_string())
        );
        assert_eq!(trycloudflare_url_bul("https://.trycloudflare.com"), None);
    }

    #[test]
    fn baslat_url_dondurur_ve_argumanlar_dogru() {
        let f = fabrika(vec![(
            url_satiri("https://a-1.trycloudflare.com"),
            Arc::new(AtomicBool::new(false)),
        )]);
        let t = TunelYoneticisi::yeni(PathBuf::from("cf.exe"), f.clone(), Duration::from_secs(2));
        let url = t.baslat(5555).unwrap();
        assert_eq!(url, "https://a-1.trycloudflare.com");
        assert!(t.aktif());
        assert_eq!(t.url(), url);
        assert_eq!(t.baslatma_sayisi(), 1);
        let args = f.argumanlar.lock().unwrap().clone();
        assert_eq!(
            args[0],
            vec![
                "tunnel",
                "--url",
                "http://127.0.0.1:5555",
                "--no-autoupdate"
            ]
        );
        // Ayni port: yeni surec acilmadan mevcut URL doner.
        assert_eq!(t.baslat(5555).unwrap(), url);
        assert_eq!(t.baslatma_sayisi(), 1);
        t.durdur();
        assert!(!t.aktif());
    }

    #[test]
    fn url_yoksa_iki_denemeden_sonra_hata() {
        let f = fabrika(vec![
            (vec!["hata".into()], Arc::new(AtomicBool::new(false))),
            (vec!["hata".into()], Arc::new(AtomicBool::new(false))),
        ]);
        let t = TunelYoneticisi::yeni(PathBuf::from("cf.exe"), f, Duration::from_millis(300));
        let sonuc = t.baslat(1234);
        assert!(sonuc.is_err());
        assert!(!t.aktif());
        assert_eq!(t.baslatma_sayisi(), 2);
        assert_eq!(t.hata(), URL_HATASI);
    }

    #[test]
    fn izleyici_surec_cikinca_bir_kez_yeniden_baslatir() {
        let bayrak1 = Arc::new(AtomicBool::new(false));
        let bayrak2 = Arc::new(AtomicBool::new(false));
        let f = fabrika(vec![
            (
                url_satiri("https://ilk-1.trycloudflare.com"),
                bayrak1.clone(),
            ),
            (
                url_satiri("https://ikinci-2.trycloudflare.com"),
                bayrak2.clone(),
            ),
        ]);
        let t = TunelYoneticisi::yeni(PathBuf::from("cf.exe"), f, Duration::from_secs(2));
        t.baslat(7777).unwrap();
        bayrak1.store(true, Ordering::SeqCst);
        let mut bekle = 0;
        while t.url() != "https://ikinci-2.trycloudflare.com" && bekle < 50 {
            thread::sleep(Duration::from_millis(100));
            bekle += 1;
        }
        assert_eq!(t.url(), "https://ikinci-2.trycloudflare.com");
        assert_eq!(t.baslatma_sayisi(), 2);
        // Ikinci cikis: yeniden deneme hakki bitti, tunel kapanir ve hata yazilir.
        bayrak2.store(true, Ordering::SeqCst);
        let mut bekle = 0;
        while t.aktif() && bekle < 50 {
            thread::sleep(Duration::from_millis(100));
            bekle += 1;
        }
        assert!(!t.aktif());
        assert_eq!(t.hata(), "Cloudflare tunnel beklenmedik sekilde kapandi");
    }

    #[test]
    fn durdur_izleyiciyi_etkisiz_kilar() {
        let bayrak = Arc::new(AtomicBool::new(false));
        let f = fabrika(vec![(
            url_satiri("https://d-3.trycloudflare.com"),
            bayrak.clone(),
        )]);
        let t = TunelYoneticisi::yeni(PathBuf::from("cf.exe"), f, Duration::from_secs(2));
        t.baslat(8080).unwrap();
        t.durdur();
        assert!(bayrak.load(Ordering::SeqCst));
        thread::sleep(Duration::from_millis(250));
        assert_eq!(t.baslatma_sayisi(), 1);
        assert!(t.url().is_empty());
    }
}
