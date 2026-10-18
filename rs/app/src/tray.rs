//! Tepsi simgesi: sol tik ve "Aç" pencereyi acar, "Çıkış" uygulamayi kapatir.

use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::AppHandle;

use crate::window;

pub fn kur(app: &AppHandle) -> tauri::Result<()> {
    let ac = MenuItem::with_id(app, "ac", "Aç", true, None::<&str>)?;
    let cik = MenuItem::with_id(app, "cik", "Çıkış", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&ac, &cik])?;

    TrayIconBuilder::with_id("afudm-tepsi")
        .tooltip("AfuDM")
        .icon(tauri::include_image!("icons/icon.png"))
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, olay| match olay.id.as_ref() {
            "ac" => window::goster(app),
            "cik" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tepsi, olay| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = olay
            {
                window::goster(tepsi.app_handle());
            }
        })
        .build(app)?;
    Ok(())
}
