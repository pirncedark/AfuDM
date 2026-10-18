//! AfuDM masaustu kabugu (Ekip F). Tek surec: tepsi simgesi her zaman; pencere
//! yalniz kullanici acinca olusur ve kapaninca WebView yok edilir. Motor
//! (aria2, store, HTTP API) arka plan thread'inde acilir.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod boot;
mod bridge;
mod kopru_g;
mod kopru_h;
mod entegrasyon;
mod guc;
mod guncelleme_zamanla;
mod izleme;
mod tray;
mod window;
mod yonetim;
mod windows_rota;

use std::sync::Arc;

use tauri::{Manager, RunEvent};

fn main() {
    let uygulama = tauri::Builder::default()
        // Ikinci acilis yeni surec baslatmaz; ilk ornegin penceresini one getirir.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            window::goster(app);
        }))
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![bridge::api_call, bridge::sayfa_hazir])
        .setup(|app| {
            let app_dir = std::env::current_exe()?
                .parent()
                .map(|p| p.to_path_buf())
                .unwrap_or_default();
            let kabuk = Arc::new(bridge::Kabuk::new(app.handle().clone(), app_dir));
            app.manage(kabuk.clone());
            tray::kur(app.handle())?;
            boot::baslat(kabuk);
            Ok(())
        })
        .build(tauri::generate_context!());

    let uygulama = match uygulama {
        Ok(u) => u,
        Err(_) => std::process::exit(1),
    };

    uygulama.run(|_app, olay| {
        // Son pencere kapaninca cikma; tepside kalir. Acik cikis (code=Some) izinli.
        if let RunEvent::ExitRequested { code: None, api, .. } = olay {
            api.prevent_exit();
        }
    });
}
