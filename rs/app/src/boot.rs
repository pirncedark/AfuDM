//! Motor acilis sirasi (Python: app.py main / core/manager.py):
//! bekleyen geri yukleme (restore_bekleyen.db -> afudm.db), cerez artiklari;
//! veri klasoru, SqliteStore, Aria2Daemon -> IdleRpc;
//! Manager (+ start, tamamlandi kancasi: otomasyon), ApiCtx;
//! with_auth(router U g1 U g2 U h), serve(port), api_endpoint.json.
//! Calisma arka plan thread'inde; pencere/tepsi beklemez.

use std::fs;
use std::sync::Arc;
use std::time::Duration;

use afudm_api::{router, serve, with_auth, write_endpoint};
use afudm_core::Manager;
use afudm_db::paths::{data_dir, db_path, default_download_dir, ensure_dirs};
use afudm_db::SqliteStore;
use afudm_engine::{Aria2Daemon, IdleRpc};
use afudm_extras::g1::automation::Otomasyon;
use afudm_extras::g1::guncelleme::Guncelleme;
use afudm_extras::g1::reliability::BEKLEYEN_GERI_YUKLEME;
use afudm_extras::g2::cerez;
use afudm_types::{ApiCtx, Aria2, ManagerApi, Store, UiBridge};

use crate::bridge::{Ek, Kabuk};

/// Ana HTTP portu. AFUDM_PORT ile degistirilir (test icin 6811 disi).
const VARSAYILAN_PORT: u16 = 6811;
const ISLEM_ZAMAN_ASIMI: Duration = Duration::from_secs(30);

pub fn port_sec() -> u16 {
    std::env::var("AFUDM_PORT")
        .ok()
        .and_then(|v| v.trim().parse::<u16>().ok())
        .unwrap_or(VARSAYILAN_PORT)
}

/// Boot'u arka plan thread'inde baslatir. Hata olursa `Kabuk::boot_hatasi` dolar.
pub fn baslat(kabuk: Arc<Kabuk>) {
    std::thread::spawn(move || {
        if let Err(hata) = calistir(&kabuk) {
            kabuk.boot_hatasi(hata);
        }
    });
}

/// Python: bekleyen geri yukleme. Store acilmadan once canli veritabanina konur.
fn bekleyen_geri_yuklemeyi_uygula(veri: &std::path::Path) -> Result<(), String> {
    let bekleyen = veri.join(BEKLEYEN_GERI_YUKLEME);
    if bekleyen.is_file() {
        let hedef = db_path(veri);
        for ek in ["-wal", "-shm"] {
            let mut yan = hedef.as_os_str().to_os_string();
            yan.push(ek);
            match fs::remove_file(yan) {
                Ok(()) => {}
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
                Err(e) => return Err(format!("geri yukleme uygulanamadi: {e}")),
            }
        }
        fs::rename(&bekleyen, hedef).map_err(|e| format!("geri yukleme uygulanamadi: {e}"))?;
    }
    Ok(())
}

fn calistir(kabuk: &Arc<Kabuk>) -> Result<(), String> {
    let app_dir = kabuk.app_dir.clone();
    let veri = data_dir(&app_dir);
    ensure_dirs(&app_dir).map_err(|e| e.to_string())?;
    bekleyen_geri_yuklemeyi_uygula(&veri)?;
    cerez::artiklari_temizle(&cerez::klasor(&veri));

    let store = Arc::new(SqliteStore::open(&db_path(&veri)).map_err(|e| e.to_string())?);
    let indirme_klasoru = match store.get("download_dir") {
        Ok(Some(serde_json::Value::String(s))) if !s.trim().is_empty() => s.into(),
        _ => default_download_dir(),
    };

    let mut daemon = Aria2Daemon::new(&app_dir, &veri, &indirme_klasoru);
    daemon.start(ISLEM_ZAMAN_ASIMI).map_err(|e| e.to_string())?;
    let idle = Arc::new(IdleRpc::new(daemon, || {}));
    let ui: Arc<dyn UiBridge> = kabuk.ui.clone();
    let manager = Arc::new(Manager::new(
        store.clone() as Arc<dyn Store>,
        idle.clone() as Arc<dyn Aria2>,
        ui.clone(),
        veri.clone(),
        app_dir.clone(),
    ));
    manager.start().map_err(|e| e.to_string())?;

    // Otomasyon: indirme bitince kuyruga ekler (Python _on_complete -> enqueue_download).
    let otomasyon = Arc::new(Otomasyon::new(store.clone() as Arc<dyn Store>, ui.clone()));
    otomasyon.start();
    {
        let otomasyon = otomasyon.clone();
        manager.tamamlandi_kancasi_ekle(Box::new(move |satir| {
            let gid = satir.get("gid").and_then(|g| g.as_str()).unwrap_or("");
            let _ = otomasyon.enqueue_download(gid, Some(satir));
        }));
    }

    let ctx = ApiCtx {
        manager: manager.clone() as Arc<dyn ManagerApi>,
        store: store as Arc<dyn Store>,
        data_dir: veri.clone(),
        app_dir: app_dir.clone(),
        ui,
    };
    // Python _on_complete: kapatma / uyku adimi (tamamlanma kancasi).
    manager.tamamlandi_kancasi_ekle(crate::guc::bitis_kancasi(ctx.clone()));
    let _ = kabuk.ctx.set(ctx.clone());

    // Tek eklenti servisi: HTTP ve kopru ayni ornegi kullanir.
    let eklenti = afudm_extras::g2::servis_olustur(&ctx);
    let guncelleme = Arc::new(Guncelleme::new(veri.clone(), app_dir.clone(), true));
    let _ = kabuk.ek.set(Ek {
        eklenti: eklenti.clone(),
        guncelleme,
        otomasyon,
        rpc: idle.clone(),
        core: manager.clone(),
    });

    crate::guncelleme_zamanla::baslat(kabuk.clone());
    crate::izleme::baslat(kabuk.clone());

    let yonlendirici = router(ctx.clone())
        .merge(afudm_extras::g1::router(ctx.clone()))
        .merge(afudm_extras::g2::router_with(ctx.clone(), eklenti))
        .merge(afudm_extras::h::router(ctx.clone()))
        .merge(crate::windows_rota::router(ctx.clone()));
    let uygulama = with_auth(yonlendirici, ctx.clone());
    crate::yonetim::yonlendiriciyi_kaydet(uygulama.clone());

    let runtime = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
        .map_err(|e| e.to_string())?;
    let port = runtime
        .block_on(serve(uygulama, port_sec()))
        .map_err(|e| e.to_string())?;
    write_endpoint(&ctx, port).map_err(|e| e.to_string())?;
    crate::yonetim::acilista(&ctx, port);
    let _ = kabuk.port.set(port);

    // Sunucu bu runtime uzerinde yasar; surec kapaninca biter.
    runtime.block_on(std::future::pending::<()>());
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fix8_restore_eski_wal_shm_temizler() {
        let d = std::env::temp_dir().join(format!("afudm-fix8-boot-{}", std::process::id()));
        fs::create_dir_all(&d).unwrap();
        fs::write(db_path(&d), b"eski").unwrap();
        fs::write(d.join(BEKLEYEN_GERI_YUKLEME), b"yeni").unwrap();
        for ek in ["-wal", "-shm"] {
            fs::write(d.join(format!("afudm.db{ek}")), b"eski").unwrap();
        }
        bekleyen_geri_yuklemeyi_uygula(&d).unwrap();
        assert_eq!(fs::read(db_path(&d)).unwrap(), b"yeni");
        for ek in ["-wal", "-shm"] {
            assert!(!d.join(format!("afudm.db{ek}")).exists());
        }
        fs::remove_dir_all(d).unwrap();
    }
}
