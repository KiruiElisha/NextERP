use std::time::Instant;

use nexterp_core::{ListQuery, Spec, Store};
use serde_json::{json, Map, Value};

fn customer_spec() -> Spec {
    Spec {
        fields: vec![],
        title: "customer_name".into(),
        search: vec!["customer_name".into(), "mobile_no".into()],
    }
}

fn row(v: Value) -> Map<String, Value> {
    v.as_object().unwrap().clone()
}

fn customers() -> Vec<Map<String, Value>> {
    vec![
        row(
            json!({"name": "CUST-1", "modified": "2026-10-01", "customer_name": "Naivas Supermarket", "mobile_no": "0712345678", "disabled": 0}),
        ),
        row(
            json!({"name": "CUST-2", "modified": "2026-10-03", "customer_name": "Quickmart Ltd", "mobile_no": "0722000000", "disabled": 0}),
        ),
        row(
            json!({"name": "CUST-3", "modified": "2026-10-02", "customer_name": "Naivasha Pharmacy", "mobile_no": "0733111222", "disabled": 1}),
        ),
    ]
}

fn store_with_customers() -> Store {
    let mut store = Store::in_memory().unwrap();
    store
        .apply("Customer", &customer_spec(), &customers(), &[])
        .unwrap();
    store
}

fn names(rows: &[Value]) -> Vec<&str> {
    rows.iter().map(|r| r["name"].as_str().unwrap()).collect()
}

#[test]
fn a_typed_prefix_finds_every_word_that_starts_with_it() {
    let store = store_with_customers();
    let hits = store.search("naiv", 10).unwrap();
    let mut found: Vec<&str> = hits.iter().map(|h| h["name"].as_str().unwrap()).collect();
    found.sort();
    assert_eq!(found, ["CUST-1", "CUST-3"]);
    assert_eq!(
        store.search("0722", 10).unwrap()[0]["title"],
        "Quickmart Ltd"
    );
}

#[test]
fn every_word_typed_must_match() {
    let store = store_with_customers();
    let hits = store.search("naiv pharm", 10).unwrap();
    assert_eq!(hits.len(), 1);
    assert_eq!(hits[0]["name"], "CUST-3");
}

#[test]
fn a_list_filters_and_sorts_on_the_rows_own_fields() {
    let store = store_with_customers();
    let q = ListQuery {
        doctype: "Customer".into(),
        filters: vec![("disabled".into(), "=".into(), json!(0))],
        order_by: Some("modified".into()),
        descending: true,
        limit: 10,
        ..Default::default()
    };
    let (rows, total) = store.list(&q).unwrap();
    assert_eq!((names(&rows), total), (vec!["CUST-2", "CUST-1"], 2));
}

#[test]
fn a_list_search_and_paging_count_the_whole_match() {
    let store = store_with_customers();
    let q = ListQuery {
        doctype: "Customer".into(),
        search: Some("naivas".into()),
        limit: 1,
        offset: 1,
        ..Default::default()
    };
    let (rows, total) = store.list(&q).unwrap();
    assert_eq!((rows.len(), total), (1, 2));
}

#[test]
fn an_unknown_operator_is_ignored_rather_than_put_into_the_query() {
    let store = store_with_customers();
    let q = ListQuery {
        doctype: "Customer".into(),
        filters: vec![("disabled".into(), "; drop table docs; --".into(), json!(0))],
        ..Default::default()
    };
    assert_eq!(store.list(&q).unwrap().1, 3);
}

#[test]
fn a_changed_row_replaces_the_old_one_and_its_search_entry() {
    let mut store = store_with_customers();
    let renamed = row(
        json!({"name": "CUST-2", "modified": "2026-10-05", "customer_name": "Carrefour", "mobile_no": ""}),
    );
    store
        .apply("Customer", &customer_spec(), &[renamed], &[])
        .unwrap();
    assert!(store.search("quickmart", 10).unwrap().is_empty());
    assert_eq!(store.search("carref", 10).unwrap()[0]["name"], "CUST-2");
    assert_eq!(
        store.get_row("Customer", "CUST-2").unwrap().unwrap()["customer_name"],
        "Carrefour"
    );
}

#[test]
fn a_deleted_row_leaves_the_list_and_the_search() {
    let mut store = store_with_customers();
    store
        .put_full("Customer", "CUST-1", &json!({"name": "CUST-1"}))
        .unwrap();
    store
        .apply("Customer", &customer_spec(), &[], &["CUST-1".into()])
        .unwrap();
    assert!(store.get_row("Customer", "CUST-1").unwrap().is_none());
    assert!(store.get_full("Customer", "CUST-1").unwrap().is_none());
    assert_eq!(store.search("naivas", 10).unwrap().len(), 1);
}

#[test]
fn the_sync_point_is_kept_per_doctype() {
    let store = Store::in_memory().unwrap();
    assert_eq!(store.since("Item").unwrap(), None);
    store
        .set_since("Item", "2026-10-27 10:00:00.123456")
        .unwrap();
    assert_eq!(
        store.since("Item").unwrap().as_deref(),
        Some("2026-10-27 10:00:00.123456")
    );
    assert_eq!(store.since("Customer").unwrap(), None);
}

#[test]
fn fifty_thousand_items_are_searched_and_listed_in_milliseconds() {
    let spec = Spec {
        fields: vec![],
        title: "item_name".into(),
        search: vec!["item_name".into(), "item_group".into()],
    };
    let groups = ["Tablets", "Syrups", "Injections", "Creams", "Devices"];
    let rows: Vec<_> = (0..50_000)
        .map(|i| row(json!({"name": format!("ITEM-{i:05}"), "modified": format!("2026-01-01 00:00:{:02}", i % 60),
            "item_name": format!("Product {i} {} {}", ["Paracetamol", "Amoxicillin", "Ibuprofen", "Cetirizine"][i % 4], i * 7),
            "item_group": groups[i % 5]})))
        .collect();
    let mut store = Store::in_memory().unwrap();
    let started = Instant::now();
    store.apply("Item", &spec, &rows, &[]).unwrap();
    let synced = started.elapsed();

    let started = Instant::now();
    let hits = store.search("amox inject", 20).unwrap();
    let searched = started.elapsed();

    let started = Instant::now();
    let q = ListQuery {
        doctype: "Item".into(),
        filters: vec![("item_group".into(), "=".into(), json!("Syrups"))],
        order_by: Some("item_name".into()),
        limit: 50,
        ..Default::default()
    };
    let (rows, total) = store.list(&q).unwrap();
    let listed = started.elapsed();

    println!(
        "50k items: stored in {synced:?}, searched in {searched:?}, filtered+sorted in {listed:?}"
    );
    assert_eq!(hits.len(), 20);
    assert_eq!((rows.len(), total), (50, 10_000));
    assert!(searched.as_millis() < 100, "search took {searched:?}");
}
