//! Pencere yasam dongusu. Pencere yalniz `goster` ile acilir; kapaninca WebView
//! yok edilir (gizlenmez), tepsi ve motor calismaya devam eder.
//! Python karsiligi: core/pencere.py (pencere_boyutu, kapatinca_gizle).

use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

pub const ANA: &str = "ana";

/// Python PENCERE_HEDEF / PENCERE_MIN (mantiksal piksel).
const HEDEF: (f64, f64) = (1600.0, 980.0);
const MIN: (f64, f64) = (1100.0, 900.0);

/// Ana pencereyi acar; zaten aciksa one getirir.
pub fn goster(app: &AppHandle) {
    match app.get_webview_window(ANA) {
        Some(w) => {
            let _ = w.unminimize();
            let _ = w.show();
            let _ = w.set_focus();
        }
        None => {
            let _ = ana_olustur(app);
        }
    }
}

/// Python pencere_boyutu: hedef, calisma alaninin %92'si ile sinirlanir;
/// min, ekran kucukse ekrana sigacak kadar daraltilir.
fn boyut(app: &AppHandle) -> (f64, f64, f64, f64) {
    let (wa_w, wa_h) = app
        .primary_monitor()
        .ok()
        .flatten()
        .map(|m| {
            let olcek = m.scale_factor();
            let s = m.size();
            (f64::from(s.width) / olcek, f64::from(s.height) / olcek)
        })
        .unwrap_or(HEDEF);
    let min_w = MIN.0.min(wa_w);
    let min_h = MIN.1.min(wa_h);
    let w = HEDEF.0.min(wa_w * 0.92).max(min_w);
    let h = HEDEF.1.min(wa_h * 0.92).max(min_h);
    (w, h, min_w, min_h)
}

fn ana_olustur(app: &AppHandle) -> tauri::Result<WebviewWindow> {
    let (w, h, min_w, min_h) = boyut(app);
    // Ozel baslik cubugu arayuzde (index.html); pencere cercevesiz acilir.
    let pencere = WebviewWindowBuilder::new(app, ANA, WebviewUrl::App("index.html".into()))
        .title("AfuDM")
        .inner_size(w, h)
        .min_inner_size(min_w, min_h)
        .center()
        .decorations(false)
        .build()?;
    Ok(pencere)
}

pub fn ana_kapat(app: &AppHandle) {
    if let Some(w) = app.get_webview_window(ANA) {
        let _ = w.close();
    }
}

pub fn indirme_kapat(app: &AppHandle) {
    if let Some(w) = app.get_webview_window(ANA) {
        let _ = w.eval("document.getElementById('kayCancel')?.click()");
    }
}
