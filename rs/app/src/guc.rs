//! Python core/manager.py _on_complete sonundaki shutdown_when_done / sleep_when_done
//! adimi ve core/guc.py. Tamamlanma kancasi olarak calisir (queue::tamamlandi sonrasi).

use std::process::Command;
use std::time::Duration;

use afudm_types::{ApiCtx, Json};

/// Python: uyutmadan once kullanicinin "vazgectim" diyebilmesi icin bekleme.
const UYKU_BEKLEME: Duration = Duration::from_secs(20);

fn acik(v: Option<Json>) -> bool {
    matches!(v, Some(Json::Bool(true)))
}

fn ayar(ctx: &ApiCtx, anahtar: &str) -> bool {
    acik(ctx.store.get(anahtar).ok().flatten())
}

/// Python _all_idle: motorda aktif/bekleyen is veya aktif video yoksa bos.
/// Snapshot okunamazsa Python'daki gibi (Aria2Error yutulur) bos sayilir.
fn tum_isler_bitti(ctx: &ApiCtx) -> bool {
    match ctx.manager.snapshot() {
        Ok(s) => !etkin_var(&s),
        Err(_) => true,
    }
}

fn etkin_var(v: &Json) -> bool {
    match v {
        Json::Object(m) => {
            matches!(m.get("status").and_then(Json::as_str), Some("active" | "waiting"))
                || m.values().any(etkin_var)
        }
        Json::Array(a) => a.iter().any(etkin_var),
        _ => false,
    }
}

fn gizli(komut: &mut Command) -> &mut Command {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        komut.creation_flags(0x0800_0000);
    }
    komut
}

/// Tamamlanma kancasi. Once kapatma, kapatma kapaliysa uyku (Python elif).
pub fn bitis_kancasi(ctx: ApiCtx) -> Box<dyn Fn(&Json) + Send + Sync> {
    Box::new(move |_satir| {
        if ayar(&ctx, "shutdown_when_done") && tum_isler_bitti(&ctx) {
            ctx.store.log("warn", "tum isler bitti — bilgisayar kapatiliyor (60 sn)", "");
            let _ = gizli(&mut Command::new("shutdown")).args([
                "/s",
                "/t",
                "60",
                "/c",
                "AfuDM: indirmeler bitti",
            ]).spawn();
        } else if ayar(&ctx, "sleep_when_done") && tum_isler_bitti(&ctx) {
            ctx.store.log("warn", "tum isler bitti — bilgisayar 20 sn sonra uyutuluyor", "");
            let ctx = ctx.clone();
            std::thread::spawn(move || {
                std::thread::sleep(UYKU_BEKLEME);
                // Python _uyut_gerekirse: yeni is geldiyse uyutma.
                if !ayar(&ctx, "sleep_when_done") || !tum_isler_bitti(&ctx) {
                    ctx.store.log("info", "uyutma iptal: yeni is var", "");
                    return;
                }
                // Python guc.uyut(): SetSuspendState(hibernate=False, force=False, wake=False).
                // ctypes yerine ayni API'yi rundll32 uzerinden cagirir.
                let basarili = gizli(&mut Command::new("rundll32.exe"))
                    .args(["powrprof.dll,SetSuspendState", "0,0,0"])
                    .status()
                    .map(|s| s.success())
                    .unwrap_or(false);
                if !basarili {
                    ctx.store.log("warn", "uyutma basarisiz (guc ayarlari engelliyor olabilir)", "");
                }
            });
        }
    })
}
