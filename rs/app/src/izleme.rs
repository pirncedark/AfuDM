//! Python core/manager.py _poll_loop karsiligi: pencere kapaliyken de tamamlanma olaylari
//! (video/indirme) isleyebilsin diye kabukta hafif yoklama. Tamamlanma snapshot okunurken
//! tetiklendiginden (queue::shaping::snapshot) yalnizca snapshot cagrilir.
//! Aralik Python'dan: POLL_INTERVAL = 0.5 sn; motor uykudayken 5 sn (Python: idle+sleeping).
//! Uykudayken snapshot CAGRILMAZ: IdleRpc her cagrida motoru uyandirir (uyku kaybolur).

use std::sync::Arc;
use std::time::Duration;

use afudm_types::Aria2;

use crate::bridge::Kabuk;

const POLL_ARALIK: Duration = Duration::from_millis(500);
const UYKU_ARALIK: Duration = Duration::from_secs(5);
const BOOT_BEKLEME: Duration = Duration::from_millis(500);

pub fn baslat(kabuk: Arc<Kabuk>) {
    std::thread::spawn(move || loop {
        let bekle = match (kabuk.ek.get(), kabuk.ctx.get()) {
            (Some(ek), Some(ctx)) => {
                if ek.rpc.sleeping() {
                    UYKU_ARALIK
                } else {
                    let _ = ctx.manager.snapshot();
                    POLL_ARALIK
                }
            }
            _ => BOOT_BEKLEME,
        };
        std::thread::sleep(bekle);
    });
}
