//! What the UI can ask of the app. Reads answer from the local cache; writes and fresh documents go
//! to the site. Every command returns the core's Error, which the UI turns into a sign-in prompt,
//! a message, or an "offline" note.

use std::sync::atomic::Ordering;
use std::sync::{Arc, Mutex};

use nexterp_core::sync::{lock, sync_all};
use nexterp_core::{Client, Error, ListQuery};
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager, State, WebviewUrl, WebviewWindowBuilder};

use crate::session::{self, AppState, Session};

type Result<T> = std::result::Result<T, Error>;

fn data_dir(app: &AppHandle) -> Result<std::path::PathBuf> {
    app.path()
        .app_data_dir()
        .map_err(|e| Error::Cache(e.to_string()))
}

/// The signed-in session as last saved, or null: the app opens on the cache, not on the network.
#[tauri::command]
pub fn session(state: State<'_, AppState>) -> Value {
    match state.current() {
        Ok(s) => json!({"site": s.site, "user": s.user, "boot": s.boot}),
        Err(_) => Value::Null,
    }
}

#[tauri::command]
pub async fn sign_in(
    app: AppHandle,
    state: State<'_, AppState>,
    site: String,
    user: String,
    password: String,
) -> Result<Value> {
    let mut client = Client::new(&site, None)?;
    client.login(user.trim(), &password).await?;
    let boot = client.get("nexterp.api.boot.boot", &Value::Null).await?;
    let user = boot["user"].as_str().unwrap_or(user.trim()).to_string();
    let dir = data_dir(&app)?;
    let store = session::open_store(&dir, client.base(), &user)?;
    store.set_kv("boot", &boot.to_string())?;
    let session = Session {
        site: client.base().to_string(),
        manifest: session::manifest_of(&boot),
        user,
        client,
        store: Arc::new(Mutex::new(store)),
        boot: boot.clone(),
    };
    session::save(&dir, &session);
    state.replace(Some(Arc::new(session)));
    start_sync(app);
    Ok(boot)
}

/// Nergaa Cloud, where the app creates new sites. NERGAA_CLOUD points it elsewhere for testing.
fn cloud_base() -> String {
    std::env::var("NERGAA_CLOUD").unwrap_or_else(|_| "https://cloud.nergaa.cloud".into())
}

/// The methods the create-a-site screens may call on Nergaa Cloud (nergaa_cloud/desktop.py).
const CLOUD_METHODS: [&str; 7] = [
    "is_available",
    "desktop_start",
    "desktop_verify",
    "desktop_options",
    "desktop_create_site",
    "desktop_site_status",
    "desktop_finish",
];

/// One step of creating a site on Nergaa Cloud. Starting over drops the old Nergaa Cloud session;
/// verifying the emailed code keeps the session it starts for the steps after it.
#[tauri::command]
pub async fn cloud(state: State<'_, AppState>, method: String, args: Value) -> Result<Value> {
    if !CLOUD_METHODS.contains(&method.as_str()) {
        return Err(Error::Server(format!(
            "{method} is not a Nergaa Cloud step"
        )));
    }
    let held = state.cloud.lock().map_err(|_| Error::SignedOut)?.clone();
    let mut client = match held {
        Some(c) if method != "desktop_start" => c,
        _ => Client::new(&cloud_base(), None)?,
    };
    let path = format!("press.api.nergaa.{method}");
    let answer = client.post_keeping_session(&path, &args).await?;
    if let Ok(mut slot) = state.cloud.lock() {
        *slot = Some(client);
    }
    Ok(answer)
}

/// A Nergaa Cloud page (the top-up, when a plan needs paying for first), signed in as the cloud step is.
#[tauri::command]
pub fn open_cloud_page(app: AppHandle, state: State<'_, AppState>, path: String) -> Result<()> {
    let sid = state
        .cloud
        .lock()
        .map_err(|_| Error::SignedOut)?
        .as_ref()
        .and_then(|c| c.sid().map(str::to_string))
        .ok_or(Error::SignedOut)?;
    let joiner = if path.contains('?') { '&' } else { '?' };
    let url = format!("{}{path}{joiner}sid={sid}", cloud_base())
        .parse()
        .map_err(|_| Error::Server("Not a valid Nergaa Cloud address".into()))?;
    let label = format!("cloud-{}", app.webview_windows().len());
    WebviewWindowBuilder::new(&app, label, WebviewUrl::External(url))
        .title("Nergaa Cloud")
        .inner_size(1100.0, 780.0)
        .build()
        .map_err(|e| Error::Server(e.to_string()))?;
    Ok(())
}

#[tauri::command]
pub async fn sign_out(app: AppHandle, state: State<'_, AppState>) -> Result<()> {
    if let Ok(s) = state.current() {
        let mut client = s.client.clone();
        client.logout().await;
    }
    state.replace(None);
    session::forget(&data_dir(&app)?);
    Ok(())
}

/// Boot again from the site (roles, companies, what is kept locally) and keep it for next launch.
#[tauri::command]
pub async fn refresh_boot(state: State<'_, AppState>) -> Result<Value> {
    let s = state.current()?;
    let boot = s.client.get("nexterp.api.boot.boot", &Value::Null).await?;
    lock(&s.store)?.set_kv("boot", &boot.to_string())?;
    let fresh = Session {
        boot: boot.clone(),
        manifest: session::manifest_of(&boot),
        client: s.client.clone(),
        store: s.store.clone(),
        site: s.site.clone(),
        user: s.user.clone(),
    };
    state.replace(Some(Arc::new(fresh)));
    Ok(boot)
}

#[tauri::command]
pub fn sync_now(app: AppHandle) {
    start_sync(app);
}

/// One sync at a time, in the background; the UI hears "sync-progress" per doctype and "sync-done".
pub fn start_sync(app: AppHandle) {
    let state = app.state::<AppState>();
    if state.syncing.swap(true, Ordering::SeqCst) {
        return;
    }
    tauri::async_runtime::spawn(async move {
        let state = app.state::<AppState>();
        let outcome = match state.current() {
            Ok(s) => {
                let emit = |doctype: &str, got: Result<usize>| {
                    let (rows, error) = match got {
                        Ok(n) => (n, None),
                        Err(e) => (0, Some(e.to_string())),
                    };
                    let _ = app.emit(
                        "sync-progress",
                        json!({"doctype": doctype, "rows": rows, "error": error}),
                    );
                };
                let result = sync_all(&s.client, &s.store, &s.manifest, emit).await;
                if result.is_ok() {
                    if let Ok(store) = lock(&s.store) {
                        let _ = store.set_kv("last_sync", &now_text());
                    }
                }
                result
            }
            Err(e) => Err(e),
        };
        state.syncing.store(false, Ordering::SeqCst);
        let _ = app.emit(
            "sync-done",
            json!({"error": outcome.err(), "at": now_text()}),
        );
    });
}

fn now_text() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    secs.to_string()
}

#[tauri::command]
pub fn list(state: State<'_, AppState>, query: ListQuery) -> Result<Value> {
    let s = state.current()?;
    let (rows, total) = lock(&s.store)?.list(&query)?;
    Ok(json!({"rows": rows, "total": total}))
}

#[tauri::command]
pub fn search(state: State<'_, AppState>, text: String, limit: Option<i64>) -> Result<Vec<Value>> {
    let s = state.current()?;
    let hits = lock(&s.store)?.search(&text, limit.unwrap_or(20));
    hits
}

/// A whole document: the cached copy at once, or the site's when asked for fresh (or none is held).
#[tauri::command]
pub async fn get_doc(
    state: State<'_, AppState>,
    doctype: String,
    name: String,
    fresh: Option<bool>,
) -> Result<Value> {
    let s = state.current()?;
    if !fresh.unwrap_or(false) {
        if let Some(doc) = lock(&s.store)?.get_full(&doctype, &name)? {
            return Ok(doc);
        }
    }
    let doc = s
        .client
        .get(
            "frappe.client.get",
            &json!({"doctype": doctype, "name": name}),
        )
        .await?;
    lock(&s.store)?.put_full(&doctype, &name, &doc)?;
    Ok(doc)
}

/// Any whitelisted method on the site. A write may name the doctype it changed, which then syncs.
#[tauri::command]
pub async fn call(
    app: AppHandle,
    state: State<'_, AppState>,
    method: String,
    args: Option<Value>,
    write: Option<bool>,
) -> Result<Value> {
    let s = state.current()?;
    let args = args.unwrap_or(Value::Null);
    let result = if write.unwrap_or(false) {
        s.client.post(&method, &args).await?
    } else {
        s.client.get(&method, &args).await?
    };
    if write.unwrap_or(false) {
        start_sync(app);
    }
    Ok(result)
}

/// A remembered answer (the home figures, the ESG year), shown at once while a fresh one loads.
#[tauri::command]
pub fn cached(state: State<'_, AppState>, key: String) -> Result<Option<Value>> {
    let s = state.current()?;
    let text = lock(&s.store)?.get_kv(&format!("cache:{key}"))?;
    Ok(text.and_then(|t| serde_json::from_str(&t).ok()))
}

#[tauri::command]
pub fn remember(state: State<'_, AppState>, key: String, value: Value) -> Result<()> {
    let s = state.current()?;
    let saved = lock(&s.store)?.set_kv(&format!("cache:{key}"), &value.to_string());
    saved
}

#[tauri::command]
pub fn cache_status(state: State<'_, AppState>) -> Result<Value> {
    let s = state.current()?;
    let store = lock(&s.store)?;
    Ok(json!({"counts": store.counts()?, "last_sync": store.get_kv("last_sync")?}))
}

#[tauri::command]
pub fn clear_cache(app: AppHandle, state: State<'_, AppState>) -> Result<()> {
    let s = state.current()?;
    lock(&s.store)?.clear()?;
    start_sync(app);
    Ok(())
}

/// ERPNext's own Desk for anything without a screen here, in a window of the app, already
/// signed in: Frappe accepts the session id in the address (it then appears in that request's log).
#[tauri::command]
pub fn open_desk(app: AppHandle, state: State<'_, AppState>, path: Option<String>) -> Result<()> {
    let s = state.current()?;
    let path = path.unwrap_or_else(|| "/app".into());
    let joiner = if path.contains('?') { '&' } else { '?' };
    let address = format!(
        "{}{}{}sid={}",
        s.site,
        path,
        joiner,
        s.client.sid().unwrap_or_default()
    );
    let url = address
        .parse()
        .map_err(|_| Error::Server("Not a valid Desk address".into()))?;
    let label = format!("desk-{}", app.webview_windows().len());
    WebviewWindowBuilder::new(&app, label, WebviewUrl::External(url))
        .title("ERPNext Desk")
        .inner_size(1280.0, 820.0)
        .build()
        .map_err(|e| Error::Server(e.to_string()))?;
    Ok(())
}
