//! Python ui/app.js guncellemeOtomatikKontrol: acilistan kisa sure sonra ve 6 saatte bir
//! kontrol (24 saat onbellek). Pencere kapaliyken de calismasi icin kabukta arka plan thread'i.
//! Otomatik guncelleme aciksa paketli kurulumda indirir; motor/indirme bos olunca uygular.

use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use afudm_extras::g1::guncelleme::Guncelleme;
use afudm_types::{ApiCtx, Json};
use serde_json::json;

use crate::bridge::{aktif_var, Kabuk};

const ACILIS_GECIKMESI: Duration = Duration::from_secs(120);
const PERIYOT: Duration = Duration::from_secs(6 * 3600);
const ONBELLEK_SN: f64 = 86400.0;
const DURUM_YOKLAMA: Duration = Duration::from_secs(5);
const BOSTA_YOKLAMA: Duration = Duration::from_secs(60);
const BEKLEME_ZAMAN_ASIMI: Duration = Duration::from_secs(6 * 3600);

fn simdi() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

/// Arka plan zamanlayicisini baslatir. Ek/ctx boot sonrasi dolar; ilk denemede hazir olmasi beklenir.
pub fn baslat(kabuk: Arc<Kabuk>) {
    std::thread::spawn(move || {
        std::thread::sleep(ACILIS_GECIKMESI);
        loop {
            if let (Some(ek), Some(ctx)) = (kabuk.ek.get(), kabuk.ctx.get()) {
                otomatik_kontrol(&ek.guncelleme, ctx, &kabuk);
            }
            std::thread::sleep(PERIYOT);
        }
    });
}

/// Python guncellemeOtomatikKontrol. Hata sessizce yutulur (Python: sessiz acilis kontrolu).
fn otomatik_kontrol(g: &Arc<Guncelleme>, ctx: &ApiCtx, kabuk: &Kabuk) {
    let Ok(once) = g.son_kontrol(&*ctx.store) else {
        return;
    };
    if once["aktif"] == json!(false) {
        return;
    }
    let zaman = once["zaman"].as_f64().unwrap_or(0.0);
    let taze = simdi() - zaman < ONBELLEK_SN;
    let bilgi = if taze { once["bilgi"].clone() } else { g.kontrol_ve_kaydet() };
    let var = bilgi["ok"] == json!(true) && bilgi["var"] == json!(true);
    if !var {
        return;
    }
    if once["paketli"] != json!(false) {
        indir_ve_bekle(g, &bilgi);
        uygula_bosta(g, ctx, kabuk);
    }
}

/// Python guncellemeBaslat(true) indirmesi: durum "bitti" ya da "hata" olana dek yoklar.
fn indir_ve_bekle(g: &Arc<Guncelleme>, bilgi: &Json) {
    let baslangic = std::time::Instant::now();
    let _ = g.clone().indir(bilgi.clone());
    while baslangic.elapsed() < BEKLEME_ZAMAN_ASIMI {
        std::thread::sleep(DURUM_YOKLAMA);
        match g.durum()["durum"].as_str() {
            Some("bitti") | Some("hata") => return,
            _ => {}
        }
    }
}

/// Python guncelleme_uygula(otomatik=True): bos degilse ("bekle") bosalana dek yeniden dener.
fn uygula_bosta(g: &Arc<Guncelleme>, ctx: &ApiCtx, kabuk: &Kabuk) {
    let baslangic = std::time::Instant::now();
    loop {
        let snap = || ctx.manager.snapshot();
        let bekleyen = ctx.manager.snapshot().map(|s| aktif_var(&s)).unwrap_or(true)
            || !kabuk.ui.listele().is_empty();
        let sonuc = g.uygula(&*ctx.store, &snap, bekleyen, true, false);
        if sonuc["bekle"] == json!(true) && baslangic.elapsed() < BEKLEME_ZAMAN_ASIMI {
            std::thread::sleep(BOSTA_YOKLAMA);
            continue;
        }
        return;
    }
}
