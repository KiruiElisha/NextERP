//! Bringing the cache up to date: each doctype's changes since its last sync, page by page.

use std::collections::BTreeMap;
use std::sync::Mutex;

use serde::Deserialize;
use serde_json::{json, Map, Value};

use crate::client::Client;
use crate::error::{Error, Result};
use crate::store::Store;

/// One doctype as the server's manifest describes it (nexterp.manifest).
#[derive(Debug, Clone, Deserialize)]
pub struct Spec {
    pub fields: Vec<String>,
    pub title: String,
    #[serde(default)]
    pub search: Vec<String>,
}

pub type Manifest = BTreeMap<String, Spec>;

const PAGE: usize = 1000;

#[derive(Deserialize)]
struct Page {
    rows: Vec<Map<String, Value>>,
    #[serde(default)]
    deleted: Vec<String>,
    until: String,
    more: bool,
}

/// Rows received for one doctype. The store's lock is held only while a page is written, never
/// across a network call, so the UI keeps reading from the cache while a sync runs.
pub async fn sync_doctype(
    client: &Client,
    store: &Mutex<Store>,
    doctype: &str,
    spec: &Spec,
) -> Result<usize> {
    let since = lock(store)?.since(doctype)?;
    let mut until: Option<String> = None;
    let mut received = 0;
    loop {
        let args = json!({"doctype": doctype, "since": since, "until": until, "start": received, "limit": PAGE});
        let page: Page =
            serde_json::from_value(client.get("nexterp.api.sync.changes", &args).await?)
                .map_err(|e| Error::Server(format!("unexpected sync reply: {e}")))?;
        lock(store)?.apply(doctype, spec, &page.rows, &page.deleted)?;
        received += page.rows.len();
        until = Some(page.until);
        if !page.more {
            break;
        }
    }
    if let Some(until) = until {
        lock(store)?.set_since(doctype, &until)?;
    }
    Ok(received)
}

/// Every doctype in the manifest, one after another. A doctype that fails is reported and the
/// rest still sync; only a lost session stops the run.
pub async fn sync_all(
    client: &Client,
    store: &Mutex<Store>,
    manifest: &Manifest,
    mut progress: impl FnMut(&str, Result<usize>),
) -> Result<()> {
    for (doctype, spec) in manifest {
        match sync_doctype(client, store, doctype, spec).await {
            Err(Error::SignedOut) => return Err(Error::SignedOut),
            outcome => progress(doctype, outcome),
        }
    }
    Ok(())
}

pub fn lock(store: &Mutex<Store>) -> Result<std::sync::MutexGuard<'_, Store>> {
    store
        .lock()
        .map_err(|_| Error::Cache("the cache is unavailable".into()))
}
