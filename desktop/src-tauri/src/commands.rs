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
    client.take_csrf(&boot);
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

/// The menu for the screen the UI shows: File appears once a site is signed in.
#[tauri::command]
pub fn set_menu(app: AppHandle, signed_in: bool) -> Result<()> {
    let menu = crate::menu(&app, signed_in).map_err(|e| Error::Server(e.to_string()))?;
    app.set_menu(menu)
        .map_err(|e| Error::Server(e.to_string()))?;
    Ok(())
}

/// Nergaa Cloud, where the app creates new sites. NERGAA_CLOUD points it elsewhere for testing.
fn cloud_base() -> String {
    std::env::var("NERGAA_CLOUD").unwrap_or_else(|_| "https://cloud.nergaa.cloud".into())
}

/// The methods the app may call on Nergaa Cloud: creating a site (nergaa_cloud/desktop.py), the
/// site's plan, invoices and apps (desktop_account.py), and topping up credits (payments/api.py).
const CLOUD_METHODS: [&str; 19] = [
    "is_available",
    "desktop_start",
    "desktop_verify",
    "desktop_options",
    "desktop_create_site",
    "desktop_site_status",
    "desktop_finish",
    "desktop_me",
    "desktop_account",
    "desktop_site_apps",
    "desktop_install_app",
    "desktop_uninstall_app",
    "desktop_change_plan",
    "options",
    "quote",
    "start",
    "status",
    "confirm",
    "history",
];

const CLOUD_SID: &str = "cloud_sid";
const CLOUD_CSRF: &str = "cloud_csrf";

/// The Nergaa Cloud session kept for the signed-in site, if any: survives restarts, and is wiped with
/// the site's cache when another user signs in on this computer.
fn saved_cloud(state: &AppState) -> Option<Client> {
    let s = state.current().ok()?;
    let store = lock(&s.store).ok()?;
    let sid = store.get_kv(CLOUD_SID).ok()??;
    let mut client = Client::new(&cloud_base(), Some(sid)).ok()?;
    if let Some(token) = store.get_kv(CLOUD_CSRF).ok()? {
        client.take_csrf(&json!({ "csrf_token": token }));
    }
    Some(client)
}

fn keep_cloud(state: &AppState, client: &Client) {
    if let (Ok(s), Some(sid)) = (state.current(), client.sid()) {
        if let Ok(store) = lock(&s.store) {
            let _ = store.set_kv(CLOUD_SID, sid);
            if let Some(token) = client.csrf() {
                let _ = store.set_kv(CLOUD_CSRF, token);
            }
        }
    }
}

/// Disconnect from Nergaa Cloud: the kept session is forgotten.
#[tauri::command]
pub fn cloud_forget(state: State<'_, AppState>) -> Result<()> {
    if let Ok(mut slot) = state.cloud.lock() {
        *slot = None;
    }
    if let Ok(s) = state.current() {
        let store = lock(&s.store)?;
        store.set_kv(CLOUD_SID, "")?;
        store.set_kv(CLOUD_CSRF, "")?;
    }
    Ok(())
}

/// A call to Nergaa Cloud. Starting over (desktop_start) drops the old session; verifying the emailed
/// code starts one, kept for the calls after it and, for a signed-in site, across restarts.
#[tauri::command]
pub async fn cloud(state: State<'_, AppState>, method: String, args: Value) -> Result<Value> {
    if !CLOUD_METHODS.contains(&method.as_str()) {
        return Err(Error::Server(format!(
            "{method} is not a Nergaa Cloud step"
        )));
    }
    let held = state.cloud.lock().map_err(|_| Error::SignedOut)?.clone();
    let held = held
        .or_else(|| saved_cloud(&state))
        .filter(|c| c.sid().is_some_and(|s| !s.is_empty()));
    let mut client = match held {
        Some(c) if method != "desktop_start" => c,
        _ => Client::new(&cloud_base(), None)?,
    };
    let path = format!("press.api.nergaa.{method}");
    let answer = client.post_keeping_session(&path, &args).await?;
    client.take_csrf(&answer);
    keep_cloud(&state, &client);
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
    let mut client = s.client.clone();
    client.take_csrf(&boot);
    let fresh = Session {
        boot: boot.clone(),
        manifest: session::manifest_of(&boot),
        client,
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

/// Any whitelisted method on the site. A write syncs the cache afterwards, unless `sync` is false.
#[tauri::command]
pub async fn call(
    app: AppHandle,
    state: State<'_, AppState>,
    method: String,
    args: Option<Value>,
    write: Option<bool>,
    sync: Option<bool>,
) -> Result<Value> {
    let s = state.current()?;
    let args = args.unwrap_or(Value::Null);
    let result = if write.unwrap_or(false) {
        s.client.post(&method, &args).await?
    } else {
        s.client.get(&method, &args).await?
    };
    // A dry run sent as a POST (a form's computed totals) changes nothing, so there's nothing to sync.
    if write.unwrap_or(false) && sync.unwrap_or(true) {
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

/// ERPNext's own Desk for anything without a screen here, or another installed app at its route
/// (`title` names its window), in a window of the app, already signed in: Frappe accepts the session id in the address (it then appears in that request's log).
#[tauri::command]
pub fn open_desk(
    app: AppHandle,
    state: State<'_, AppState>,
    path: Option<String>,
    title: Option<String>,
) -> Result<()> {
    let s = state.current()?;
    let path = path.unwrap_or_else(|| "/app".into());
    let url = desk_url(&s.site, &path, &s.client.sid().unwrap_or_default())?;
    let label = format!("desk-{}", app.webview_windows().len());
    WebviewWindowBuilder::new(&app, label, WebviewUrl::External(url))
        .title(title.as_deref().unwrap_or("ERPNext Desk"))
        .inner_size(1280.0, 820.0)
        .build()
        .map_err(|e| Error::Server(e.to_string()))?;
    Ok(())
}

/// The Desk address for a path on the signed-in site, with the session so Desk opens signed in.
/// Only a path on that same site is accepted: the session id must never go to another host (a
/// "path" like "@evil.example/" or "//evil.example/" would otherwise send it there).
fn desk_url(site: &str, path: &str, sid: &str) -> Result<tauri::Url> {
    let bad = || Error::Server("Not a valid Desk address".into());
    if !path.starts_with('/') || path.starts_with("//") || path.contains('\\') {
        return Err(bad());
    }
    let base: tauri::Url = site.parse().map_err(|_| bad())?;
    let mut url = base.join(path).map_err(|_| bad())?;
    if url.origin() != base.origin() {
        return Err(bad());
    }
    url.query_pairs_mut().append_pair("sid", sid);
    Ok(url)
}

/// A file from the site (a document's PDF) saved in the computer's Downloads folder. A name
/// already there gets " (2)", " (3)"... so nothing is overwritten. Returns the path written.
#[tauri::command]
pub async fn save_file(
    app: AppHandle,
    state: State<'_, AppState>,
    method: String,
    args: Option<Value>,
    filename: String,
) -> Result<String> {
    let s = state.current()?;
    let bytes = s
        .client
        .get_bytes(&method, &args.unwrap_or(Value::Null))
        .await?;
    let dir = app
        .path()
        .download_dir()
        .map_err(|e| Error::Cache(e.to_string()))?;
    let safe: String = filename
        .chars()
        .map(|c| if "/\\:*?\"<>|".contains(c) { '-' } else { c })
        .collect();
    let (stem, ext) = match safe.rsplit_once('.') {
        Some((a, b)) => (a.to_string(), format!(".{b}")),
        None => (safe.clone(), String::new()),
    };
    let mut path = dir.join(&safe);
    let mut n = 2;
    while path.exists() {
        path = dir.join(format!("{stem} ({n}){ext}"));
        n += 1;
    }
    std::fs::write(&path, bytes).map_err(|e| Error::Cache(e.to_string()))?;
    Ok(path.to_string_lossy().into_owned())
}

/// A payment provider's checkout (card or PayPal top-ups), in a window of the app: the one page that
/// can't be drawn here, since card details are entered on the provider's own page. Only https pages
/// on the providers' own domains are opened.
#[tauri::command]
pub fn open_checkout(app: AppHandle, url: String) -> Result<()> {
    const PROVIDERS: [&str; 3] = ["paypal.com", "intasend.com", "sandbox.paypal.com"];
    let parsed: tauri::Url = url
        .parse()
        .map_err(|_| Error::Server("Not a checkout address".into()))?;
    let host = parsed.host_str().unwrap_or_default().to_ascii_lowercase();
    let allowed = parsed.scheme() == "https"
        && PROVIDERS
            .iter()
            .any(|p| host == *p || host.ends_with(&format!(".{p}")));
    if !allowed {
        return Err(Error::Server(format!(
            "{host} isn't a payment provider the app opens"
        )));
    }
    let label = format!("checkout-{}", app.webview_windows().len());
    WebviewWindowBuilder::new(&app, label, WebviewUrl::External(parsed))
        .title("Checkout")
        .inner_size(900.0, 760.0)
        .build()
        .map_err(|e| Error::Server(e.to_string()))?;
    Ok(())
}

#[cfg(test)]
mod desk_tests {
    use super::desk_url;

    #[test]
    fn desk_paths_stay_on_the_site() {
        let ok = desk_url("https://acme.nergaa.cloud", "/app/item?x=1", "abc").unwrap();
        assert_eq!(
            ok.as_str(),
            "https://acme.nergaa.cloud/app/item?x=1&sid=abc"
        );
        for evil in [
            "@evil.example/x",
            "//evil.example/x",
            "/\\evil.example",
            "https://evil.example/",
            "app",
        ] {
            assert!(
                desk_url("https://acme.nergaa.cloud", evil, "abc").is_err(),
                "{evil}"
            );
        }
    }
}
