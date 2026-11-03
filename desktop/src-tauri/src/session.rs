//! Who is signed in to which site, kept between launches so the app opens straight into its cache.

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};

use nexterp_core::{Client, Error, Manifest, Store};
use serde::{Deserialize, Serialize};
use serde_json::Value;

pub struct Session {
    pub site: String,
    pub user: String,
    pub client: Client,
    pub store: Arc<Mutex<Store>>,
    pub boot: Value,
    pub manifest: Manifest,
}

#[derive(Default)]
pub struct AppState {
    pub session: Mutex<Option<Arc<Session>>>,
    pub syncing: AtomicBool,
    /// Signed in to Nergaa Cloud (Press) while creating a site; never saved to disk.
    pub cloud: Mutex<Option<Client>>,
}

impl AppState {
    pub fn current(&self) -> Result<Arc<Session>, Error> {
        self.session
            .lock()
            .map_err(|_| Error::SignedOut)?
            .clone()
            .ok_or(Error::SignedOut)
    }

    pub fn replace(&self, session: Option<Arc<Session>>) {
        if let Ok(mut slot) = self.session.lock() {
            *slot = session;
        }
    }
}

/// What survives a restart: the site, the user and Frappe's session id. Not the password.
#[derive(Serialize, Deserialize)]
struct Saved {
    site: String,
    user: String,
    sid: String,
}

pub fn manifest_of(boot: &Value) -> Manifest {
    serde_json::from_value(boot["manifest"].clone()).unwrap_or_default()
}

/// The cache file for one site: each site keeps its own, so switching sites never mixes data.
pub fn cache_path(dir: &Path, site: &str) -> PathBuf {
    let slug: String = site
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() { c } else { '_' })
        .collect();
    dir.join("cache").join(format!("{slug}.sqlite"))
}

pub fn open_store(dir: &Path, site: &str, user: &str) -> Result<Store, Error> {
    let path = cache_path(dir, site);
    fs::create_dir_all(path.parent().unwrap()).map_err(|e| Error::Cache(e.to_string()))?;
    let store = Store::open(&path)?;
    // Another user on the same computer must not see what the last one could.
    if store.get_kv("user")?.as_deref() != Some(user) {
        store.clear()?;
        store.set_kv("user", user)?;
    }
    Ok(store)
}

pub fn save(dir: &Path, session: &Session) {
    let saved = Saved {
        site: session.site.clone(),
        user: session.user.clone(),
        sid: session.client.sid().unwrap_or_default().to_string(),
    };
    let _ = fs::create_dir_all(dir);
    let _ = fs::write(
        dir.join("session.json"),
        serde_json::to_string(&saved).unwrap_or_default(),
    );
}

pub fn forget(dir: &Path) {
    let _ = fs::remove_file(dir.join("session.json"));
}

/// The last session, rebuilt from disk without the network: the UI shows the cache at once.
pub fn restore(dir: &Path) -> Option<Session> {
    let saved: Saved =
        serde_json::from_str(&fs::read_to_string(dir.join("session.json")).ok()?).ok()?;
    let store = open_store(dir, &saved.site, &saved.user).ok()?;
    let boot: Value = serde_json::from_str(&store.get_kv("boot").ok()??).ok()?;
    Some(Session {
        client: Client::new(&saved.site, Some(saved.sid)).ok()?,
        manifest: manifest_of(&boot),
        site: saved.site,
        user: saved.user,
        store: Arc::new(Mutex::new(store)),
        boot,
    })
}
