//! Against a real ERPNext site with nexterp installed. Runs only when told where:
//!     NEXTERP_TEST_SITE=http://site:8000 NEXTERP_TEST_USER=... NEXTERP_TEST_PASSWORD=... cargo test --test live

use std::sync::Mutex;

use nexterp_core::sync::{sync_all, sync_doctype};
use nexterp_core::{Client, Error, ListQuery, Manifest, Store};
use serde_json::{json, Value};

fn site() -> Option<(String, String, String)> {
    let get = |k| std::env::var(k).ok();
    Some((
        get("NEXTERP_TEST_SITE")?,
        get("NEXTERP_TEST_USER")?,
        get("NEXTERP_TEST_PASSWORD")?,
    ))
}

async fn signed_in() -> Option<Client> {
    let (site, user, password) = site()?;
    let mut client = Client::new(&site, None).unwrap();
    client.login(&user, &password).await.unwrap();
    Some(client)
}

async fn manifest(client: &Client) -> Manifest {
    let boot = client
        .get("nexterp.api.boot.boot", &Value::Null)
        .await
        .unwrap();
    serde_json::from_value(boot["manifest"].clone()).unwrap()
}

#[tokio::test]
async fn a_first_sync_fills_the_cache_and_the_next_one_brings_only_changes() {
    let Some(client) = signed_in().await else {
        return;
    };
    let manifest = manifest(&client).await;
    let store = Mutex::new(Store::in_memory().unwrap());

    let mut first = 0;
    sync_all(&client, &store, &manifest, |_, got| first += got.unwrap())
        .await
        .unwrap();
    let customers = store
        .lock()
        .unwrap()
        .list(&ListQuery {
            doctype: "Customer".into(),
            ..Default::default()
        })
        .unwrap()
        .1;
    assert!(
        first > 0 && customers > 0,
        "first sync brought {first} rows, {customers} customers"
    );

    let again = sync_doctype(&client, &store, "Customer", &manifest["Customer"])
        .await
        .unwrap();
    assert!(
        again < customers as usize,
        "a second sync re-sent {again} of {customers} customers"
    );
}

#[tokio::test]
async fn a_new_customer_on_the_site_reaches_the_cache_on_the_next_sync() {
    let Some(client) = signed_in().await else {
        return;
    };
    let manifest = manifest(&client).await;
    let store = Mutex::new(Store::in_memory().unwrap());
    sync_doctype(&client, &store, "Customer", &manifest["Customer"])
        .await
        .unwrap();

    let name = format!("Live Sync {}", std::process::id());
    let made = client
        .post(
            "frappe.client.insert",
            &json!({"doc": {"doctype": "Customer", "customer_name": name}}),
        )
        .await
        .unwrap();
    sync_doctype(&client, &store, "Customer", &manifest["Customer"])
        .await
        .unwrap();
    let hits = store.lock().unwrap().search(&name, 5).unwrap();
    client
        .post(
            "frappe.client.delete",
            &json!({"doctype": "Customer", "name": made["name"]}),
        )
        .await
        .unwrap();

    assert_eq!(hits.first().map(|h| h["title"].clone()), Some(json!(name)));
    sync_doctype(&client, &store, "Customer", &manifest["Customer"])
        .await
        .unwrap();
    assert!(
        store.lock().unwrap().search(&name, 5).unwrap().is_empty(),
        "the deleted customer stayed in the cache"
    );
}

#[tokio::test]
async fn a_wrong_password_is_reported_and_a_dead_session_reads_as_signed_out() {
    let Some((site, user, _)) = site() else {
        return;
    };
    let mut client = Client::new(&site, None).unwrap();
    let wrong = client.login(&user, "not-the-password").await.unwrap_err();
    assert!(
        matches!(wrong, Error::Server(ref m) if m.contains("Wrong")),
        "{wrong:?}"
    );

    let expired = Client::new(&site, Some("no-such-session".into())).unwrap();
    let err = expired
        .get("nexterp.api.boot.boot", &Value::Null)
        .await
        .unwrap_err();
    assert!(matches!(err, Error::SignedOut), "{err:?}");
}

#[tokio::test]
async fn the_sites_refusal_comes_back_in_its_own_words() {
    let Some(client) = signed_in().await else {
        return;
    };
    let err = client
        .get("nexterp.api.sync.changes", &json!({"doctype": "User"}))
        .await
        .unwrap_err();
    assert!(
        matches!(err, Error::Server(ref m) if m.contains("not kept on the desktop")),
        "{err:?}"
    );
}
