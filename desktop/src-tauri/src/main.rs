// NextERP, a desktop app for ERPNext. The window shows the bundled UI (desktop/ui); the data it shows comes from
// the local cache (nexterp-core), kept in step with the site in the background.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod docker;
mod docker_install;
mod session;

use std::time::Duration;

use tauri::menu::{Menu, MenuItem, PredefinedMenuItem, Submenu};
use tauri::{Emitter, Manager};

use session::AppState;

/// How often the cache catches up while the app is open, on top of syncing after every write.
const SYNC_EVERY: Duration = Duration::from_secs(5 * 60);

/// WebKitGTK's GPU paths that leave a blank window (its DMA-BUF renderer, on NVIDIA and some Wayland
/// setups) or end the app after a few minutes (explicit sync on NVIDIA under Wayland: "Error 71").
/// Set before GTK starts; a value the user already exported wins.
#[cfg(target_os = "linux")]
fn safe_linux_rendering() {
    for (name, value) in [
        ("WEBKIT_DISABLE_DMABUF_RENDERER", "1"),
        ("__NV_DISABLE_EXPLICIT_SYNC", "1"),
    ] {
        if std::env::var_os(name).is_none() {
            std::env::set_var(name, value); // first thing in main: no other thread reads the environment yet
        }
    }
}

fn main() {
    #[cfg(target_os = "linux")]
    safe_linux_rendering();
    tauri::Builder::default()
        .manage(AppState::default())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            // Updates are signed: the release build adds the public key (plugins.updater) only when
            // the signing key is set up, so a build without it starts normally and never updates.
            if app.config().plugins.0.contains_key("updater") {
                app.handle()
                    .plugin(tauri_plugin_updater::Builder::new().build())?;
            }
            if let Ok(dir) = app.path().app_data_dir() {
                let restored = session::restore(&dir).map(std::sync::Arc::new);
                app.state::<AppState>().replace(restored);
            }
            let signed_in = app.state::<AppState>().current().is_ok();
            app.set_menu(menu(app.handle(), signed_in)?)?;
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
            commands::outbox_add,
            commands::outbox_list,
            commands::outbox_delete,
            commands::outbox_send,
            commands::outbox_mark,
            commands::sign_in,
            commands::cloud,
            commands::open_cloud_page,
            commands::cloud_forget,
            commands::open_checkout,
            commands::set_menu,
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
            commands::open_in_browser,
            commands::save_file,
            docker::local_docker_status,
            docker::local_docker_install,
            docker::local_docker_setup,
            docker::local_docker_start,
        ])
        .run(tauri::generate_context!())
        .expect("error while running NextERP");
}

/// The window's menu. File (new invoice, search, sync, Desk, sign out) only once a site is signed in:
/// before that its items have nothing to act on.
pub fn menu(app: &tauri::AppHandle, signed_in: bool) -> tauri::Result<Menu<tauri::Wry>> {
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
            &item("switch", "Switch App…", Some("CmdOrCtrl+Shift+O"))?,
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
    if signed_in {
        Menu::with_items(app, &[&file, &edit, &view])
    } else {
        Menu::with_items(app, &[&edit, &view])
    }
}
