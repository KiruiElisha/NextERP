// ERPNext on the desktop. The window shows the bundled UI (desktop/ui); the data it shows comes from
// the local cache (nexterp-core), kept in step with the site in the background.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod session;

use std::time::Duration;

use tauri::menu::{Menu, MenuItem, PredefinedMenuItem, Submenu};
use tauri::{Emitter, Manager};

use session::AppState;

/// How often the cache catches up while the app is open, on top of syncing after every write.
const SYNC_EVERY: Duration = Duration::from_secs(5 * 60);

fn main() {
    tauri::Builder::default()
        .manage(AppState::default())
        .setup(|app| {
            if let Ok(dir) = app.path().app_data_dir() {
                let restored = session::restore(&dir).map(std::sync::Arc::new);
                app.state::<AppState>().replace(restored);
            }
            app.set_menu(menu(app.handle())?)?;
            app.on_menu_event(|app, event| {
                // The UI owns what each item does: it knows the screen it is on.
                let _ = app.emit("menu", event.id().as_ref());
            });
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                loop {
                    commands::start_sync(handle.clone());
                    tokio::time::sleep(SYNC_EVERY).await;
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::session,
            commands::sign_in,
            commands::sign_out,
            commands::refresh_boot,
            commands::sync_now,
            commands::list,
            commands::search,
            commands::get_doc,
            commands::call,
            commands::cached,
            commands::remember,
            commands::cache_status,
            commands::clear_cache,
            commands::open_desk,
        ])
        .run(tauri::generate_context!())
        .expect("error while running the ERPNext desktop app");
}

fn menu(app: &tauri::AppHandle) -> tauri::Result<Menu<tauri::Wry>> {
    let item =
        |id: &str, label: &str, accel: Option<&str>| MenuItem::with_id(app, id, label, true, accel);
    let file = Submenu::with_items(
        app,
        "File",
        true,
        &[
            &item("new-invoice", "New Sales Invoice", Some("CmdOrCtrl+N"))?,
            &item("search", "Search…", Some("CmdOrCtrl+K"))?,
            &item("sync", "Sync now", Some("CmdOrCtrl+Shift+S"))?,
            &item("desk", "Open ERPNext Desk", Some("CmdOrCtrl+Shift+D"))?,
            &PredefinedMenuItem::separator(app)?,
            &item("sign-out", "Sign out", None)?,
            &PredefinedMenuItem::quit(app, None)?,
        ],
    )?;
    let edit = Submenu::with_items(
        app,
        "Edit",
        true,
        &[
            &PredefinedMenuItem::undo(app, None)?,
            &PredefinedMenuItem::redo(app, None)?,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::cut(app, None)?,
            &PredefinedMenuItem::copy(app, None)?,
            &PredefinedMenuItem::paste(app, None)?,
            &PredefinedMenuItem::select_all(app, None)?,
        ],
    )?;
    let view = Submenu::with_items(
        app,
        "View",
        true,
        &[
            &item("reload", "Reload", Some("CmdOrCtrl+R"))?,
            &PredefinedMenuItem::fullscreen(app, None)?,
        ],
    )?;
    Menu::with_items(app, &[&file, &edit, &view])
}
