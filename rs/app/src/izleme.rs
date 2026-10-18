//! Python _poll_loop: snapshot okuyucusu olmadan DB ve tamamlanma senkronu.
//! POLL_INTERVAL = 0.5 sn; motor uykudayken 5 sn, RPC ile uyandirilmaz.

use std::sync::Arc;
use std::time::{Duration, Instant};

use afudm_types::Aria2;

use crate::bridge::Kabuk;

const POLL_ARALIK: Duration = Duration::from_millis(500);
const UYKU_ARALIK: Duration = Duration::from_secs(5);
const BOOT_BEKLEME: Duration = Duration::from_millis(500);
const BOSTA_KONTROL: Duration = Duration::from_secs(30);

pub fn baslat(kabuk: Arc<Kabuk>) {
    std::thread::spawn(move || {
        let mut son_uyku_kontrolu = Instant::now();
        loop {
            let bekle = match (kabuk.ek.get(), kabuk.ctx.get()) {
                (Some(ek), Some(ctx)) => {
                    // Video completion must drain even while aria2 sleeps.
                    let synced = afudm_core::queue::sync_aria2(&ek.core).is_ok();
                    if synced && son_uyku_kontrolu.elapsed() >= BOSTA_KONTROL {
                        son_uyku_kontrolu = Instant::now();
                        // A download may finish between sync and sleep_if_idle.
                        // Until its DB row is synced, active/queued state blocks
                        // purge. Never run a separate unsynchronized idle thread.
                        let pending = ["active", "waiting", "queued", "scheduled", "repairing"]
                            .iter()
                            .any(|status| {
                                ctx.store
                                    .list(Some(status), 1)
                                    .map(|rows| !rows.is_empty())
                                    .unwrap_or(true)
                            });
                        if !pending && !ek.rpc.sleeping() {
                            let _ = ek.rpc.sleep_if_idle();
                        }
                    }
                    if ek.rpc.sleeping() {
                        UYKU_ARALIK
                    } else {
                        POLL_ARALIK
                    }
                }
                _ => BOOT_BEKLEME,
            };
            std::thread::sleep(bekle);
        }
    });
}
