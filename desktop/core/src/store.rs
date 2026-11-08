//! The local cache: one SQLite file per site and user, holding synced rows as JSON and a full-text
//! index over their titles, so lists, filters and search answer without the network.

use std::path::Path;

use rusqlite::{params, params_from_iter, Connection, OptionalExtension};
use serde::Deserialize;
use serde_json::{Map, Value};

use crate::error::Result;
use crate::sync::Spec;

const SCHEMA: &str = "
    pragma journal_mode = wal;
    pragma synchronous = normal;
    create table if not exists docs (
        doctype text not null, name text not null, modified text, data text not null,
        primary key (doctype, name)
    );
    create virtual table if not exists search using fts5 (
        doctype unindexed, name unindexed, title, body,
        tokenize = 'unicode61 remove_diacritics 2', prefix = '2 3'
    );
    create table if not exists full_docs (
        doctype text not null, name text not null, data text not null, primary key (doctype, name)
    );
    create table if not exists sync_state (doctype text primary key, since text, synced_at text);
    create table if not exists kv (key text primary key, value text not null);
    create table if not exists outbox (
        id text primary key, user text not null, doctype text not null, doc text not null,
        title text, created integer not null, status text not null default 'pending', error text
    );
    create index if not exists outbox_user on outbox (user, created);
";

/// Drafts kept while the site can't be reached: at most this many per user, each at most this big.
pub const OUTBOX_MAX: i64 = 500;
pub const OUTBOX_MAX_BYTES: usize = 1_000_000;

const OPERATORS: [&str; 7] = ["=", "!=", ">", "<", ">=", "<=", "like"];

pub struct Store {
    conn: Connection,
}

/// A list screen's question: which doctype, narrowed how, in what order, which page.
#[derive(Debug, Default, Deserialize)]
pub struct ListQuery {
    pub doctype: String,
    #[serde(default)]
    pub search: Option<String>,
    /// `[field, operator, value]`, all of which must hold.
    #[serde(default)]
    pub filters: Vec<(String, String, Value)>,
    #[serde(default)]
    pub order_by: Option<String>,
    #[serde(default)]
    pub descending: bool,
    #[serde(default = "default_limit")]
    pub limit: i64,
    #[serde(default)]
    pub offset: i64,
}

fn default_limit() -> i64 {
    100
}

impl Store {
    pub fn open(path: &Path) -> Result<Self> {
        Self::init(Connection::open(path)?)
    }

    pub fn in_memory() -> Result<Self> {
        Self::init(Connection::open_in_memory()?)
    }

    fn init(conn: Connection) -> Result<Self> {
        conn.execute_batch(SCHEMA)?;
        Ok(Store { conn })
    }

    /// Store a page of synced rows and drop deleted ones, in one transaction.
    pub fn apply(
        &mut self,
        doctype: &str,
        spec: &Spec,
        rows: &[Map<String, Value>],
        deleted: &[String],
    ) -> Result<()> {
        let tx = self.conn.transaction()?;
        for row in rows {
            let name = text(row.get("name"));
            let rowid: i64 = tx.query_row(
                "insert into docs (doctype, name, modified, data) values (?1, ?2, ?3, ?4)
                 on conflict (doctype, name) do update set modified = excluded.modified, data = excluded.data
                 returning rowid",
                params![doctype, name, text(row.get("modified")), Value::Object(row.clone()).to_string()],
                |r| r.get(0),
            )?;
            tx.execute("delete from search where rowid = ?1", [rowid])?;
            tx.execute(
                "insert into search (rowid, doctype, name, title, body) values (?1, ?2, ?3, ?4, ?5)",
                params![rowid, doctype, name, title_of(row, spec, &name), body_of(row, spec, &name)],
            )?;
        }
        for name in deleted {
            forget(&tx, doctype, name)?;
        }
        tx.commit()?;
        Ok(())
    }

    /// One page of a list, and how many rows match in all.
    pub fn list(&self, q: &ListQuery) -> Result<(Vec<Value>, i64)> {
        let mut clauses = vec!["d.doctype = ?".to_string()];
        let mut values: Vec<Value> = vec![Value::from(q.doctype.clone())];
        if let Some(fts) = q.search.as_deref().and_then(match_expression) {
            clauses.push("d.rowid in (select rowid from search where search match ?)".into());
            values.push(Value::from(fts));
        }
        for (field, op, value) in &q.filters {
            let op = op.to_lowercase();
            if !OPERATORS.contains(&op.as_str()) {
                continue;
            }
            clauses.push(format!("json_extract(d.data, ?) {op} ?"));
            values.push(Value::from(format!("$.{field}")));
            values.push(value.clone());
        }
        let filter = clauses.join(" and ");
        let total: i64 = self.conn.query_row(
            &format!("select count(*) from docs d where {filter}"),
            params_from_iter(values.iter().map(sql_value)),
            |r| r.get(0),
        )?;
        let order = format!("$.{}", q.order_by.as_deref().unwrap_or("modified"));
        let direction = if q.descending { "desc" } else { "asc" };
        let sql = format!(
            "select d.data from docs d where {filter} order by json_extract(d.data, ?) {direction}, d.name limit ? offset ?"
        );
        values.extend([
            Value::from(order),
            Value::from(q.limit),
            Value::from(q.offset),
        ]);
        let mut stmt = self.conn.prepare_cached(&sql)?;
        let rows = stmt
            .query_map(params_from_iter(values.iter().map(sql_value)), |r| {
                r.get::<_, String>(0)
            })?
            .filter_map(|s| s.ok().and_then(|s| serde_json::from_str(&s).ok()))
            .collect();
        Ok((rows, total))
    }

    /// Everything matching what was typed, across doctypes, best first: the Ctrl+K search.
    pub fn search(&self, typed: &str, limit: i64) -> Result<Vec<Value>> {
        let Some(fts) = match_expression(typed) else {
            return Ok(vec![]);
        };
        let mut stmt = self.conn.prepare_cached(
            "select doctype, name, title from search where search match ?1 order by bm25(search, 0, 0, 4, 1) limit ?2",
        )?;
        let hits = stmt
            .query_map(params![fts, limit], |r| {
                Ok(serde_json::json!({"doctype": r.get::<_, String>(0)?, "name": r.get::<_, String>(1)?, "title": r.get::<_, String>(2)?}))
            })?
            .filter_map(|h| h.ok())
            .collect();
        Ok(hits)
    }

    pub fn get_row(&self, doctype: &str, name: &str) -> Result<Option<Value>> {
        self.json(
            "select data from docs where doctype = ?1 and name = ?2",
            doctype,
            name,
        )
    }

    /// A whole document as last fetched from the site, so reopening it is instant.
    pub fn get_full(&self, doctype: &str, name: &str) -> Result<Option<Value>> {
        self.json(
            "select data from full_docs where doctype = ?1 and name = ?2",
            doctype,
            name,
        )
    }

    pub fn put_full(&self, doctype: &str, name: &str, doc: &Value) -> Result<()> {
        self.conn.execute(
            "insert into full_docs (doctype, name, data) values (?1, ?2, ?3)
             on conflict (doctype, name) do update set data = excluded.data",
            params![doctype, name, doc.to_string()],
        )?;
        Ok(())
    }

    pub fn since(&self, doctype: &str) -> Result<Option<String>> {
        Ok(self
            .conn
            .query_row(
                "select since from sync_state where doctype = ?1",
                [doctype],
                |r| r.get(0),
            )
            .optional()?
            .flatten())
    }

    pub fn set_since(&self, doctype: &str, until: &str) -> Result<()> {
        self.conn.execute(
            "insert into sync_state (doctype, since, synced_at) values (?1, ?2, datetime('now'))
             on conflict (doctype) do update set since = excluded.since, synced_at = excluded.synced_at",
            params![doctype, until],
        )?;
        Ok(())
    }

    /// Rows held per doctype, for the sync status in the app.
    pub fn counts(&self) -> Result<Map<String, Value>> {
        let mut stmt = self
            .conn
            .prepare("select doctype, count(*) from docs group by doctype")?;
        let counts = stmt
            .query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, i64>(1)?)))?
            .filter_map(|c| c.ok())
            .map(|(d, n)| (d, Value::from(n)))
            .collect();
        Ok(counts)
    }

    pub fn get_kv(&self, key: &str) -> Result<Option<String>> {
        Ok(self
            .conn
            .query_row("select value from kv where key = ?1", [key], |r| r.get(0))
            .optional()?)
    }

    pub fn set_kv(&self, key: &str, value: &str) -> Result<()> {
        self.conn.execute(
            "insert into kv (key, value) values (?1, ?2) on conflict (key) do update set value = excluded.value",
            params![key, value],
        )?;
        Ok(())
    }

    pub fn delete_kv(&self, key: &str) -> Result<()> {
        self.conn.execute("delete from kv where key = ?1", [key])?;
        Ok(())
    }

    /// Everything one user saw, for a sign-in as someone else: the synced rows and the answers kept
    /// for screens (figures, form definitions) and the Nergaa Cloud session. Unsent drafts stay,
    /// each kept for its own user (`outbox`), and nobody else is shown them.
    pub fn forget_user(&self) -> Result<()> {
        self.clear()?;
        self.conn.execute_batch(
            "delete from kv where key like 'cache:%' or key in ('cloud_sid', 'cloud_csrf', 'boot', 'last_sync');",
        )?;
        Ok(())
    }

    // ── Drafts made offline, sent when the site is back ─────────────────────────────────────

    /// Keep a new draft for `user`. Refused when it is too big or the user already has too many,
    /// so a stuck site can't fill the computer.
    pub fn outbox_add(
        &self,
        user: &str,
        id: &str,
        doctype: &str,
        doc: &Value,
        title: &str,
        now: i64,
    ) -> Result<()> {
        let text = doc.to_string();
        if text.len() > OUTBOX_MAX_BYTES {
            return Err(crate::error::Error::Cache(
                "this draft is too big to keep offline".into(),
            ));
        }
        if self.outbox_count(user)? >= OUTBOX_MAX {
            return Err(crate::error::Error::Cache(format!(
                "{OUTBOX_MAX} drafts are already waiting to be sent; send or delete some first"
            )));
        }
        self.conn.execute(
            "insert into outbox (id, user, doctype, doc, title, created) values (?1, ?2, ?3, ?4, ?5, ?6)
             on conflict (id) do update set doc = excluded.doc, title = excluded.title, status = 'pending', error = null
             where outbox.user = excluded.user",
            params![id, user, doctype, text, title, now],
        )?;
        Ok(())
    }

    pub fn outbox_count(&self, user: &str) -> Result<i64> {
        Ok(self
            .conn
            .query_row("select count(*) from outbox where user = ?1", [user], |r| {
                r.get(0)
            })?)
    }

    /// This user's drafts, oldest first (the order they are sent in).
    pub fn outbox_list(&self, user: &str) -> Result<Vec<Value>> {
        let mut st = self.conn.prepare(
            "select id, doctype, doc, title, created, status, error from outbox where user = ?1 order by created, id",
        )?;
        let rows = st.query_map([user], |r| {
            let doc: String = r.get(2)?;
            Ok(serde_json::json!({
                "id": r.get::<_, String>(0)?,
                "doctype": r.get::<_, String>(1)?,
                "doc": serde_json::from_str::<Value>(&doc).unwrap_or(Value::Null),
                "title": r.get::<_, Option<String>>(3)?,
                "created": r.get::<_, i64>(4)?,
                "status": r.get::<_, String>(5)?,
                "error": r.get::<_, Option<String>>(6)?,
            }))
        })?;
        Ok(rows.collect::<std::result::Result<_, _>>()?)
    }

    pub fn outbox_mark(
        &self,
        user: &str,
        id: &str,
        status: &str,
        error: Option<&str>,
    ) -> Result<()> {
        self.conn.execute(
            "update outbox set status = ?3, error = ?4 where id = ?1 and user = ?2",
            params![id, user, status, error],
        )?;
        Ok(())
    }

    pub fn outbox_delete(&self, user: &str, id: &str) -> Result<()> {
        self.conn.execute(
            "delete from outbox where id = ?1 and user = ?2",
            params![id, user],
        )?;
        Ok(())
    }

    /// Everything synced, for "Clear cache" and a sign-in as someone else.
    pub fn clear(&self) -> Result<()> {
        self.conn.execute_batch(
            "delete from docs; delete from search; delete from full_docs; delete from sync_state;",
        )?;
        Ok(())
    }

    fn json(&self, sql: &str, doctype: &str, name: &str) -> Result<Option<Value>> {
        let data: Option<String> = self
            .conn
            .query_row(sql, params![doctype, name], |r| r.get(0))
            .optional()?;
        Ok(data.and_then(|d| serde_json::from_str(&d).ok()))
    }
}

fn forget(tx: &rusqlite::Transaction, doctype: &str, name: &str) -> Result<()> {
    let rowid: Option<i64> = tx
        .query_row(
            "select rowid from docs where doctype = ?1 and name = ?2",
            params![doctype, name],
            |r| r.get(0),
        )
        .optional()?;
    if let Some(rowid) = rowid {
        tx.execute("delete from search where rowid = ?1", [rowid])?;
        tx.execute("delete from docs where rowid = ?1", [rowid])?;
    }
    tx.execute(
        "delete from full_docs where doctype = ?1 and name = ?2",
        params![doctype, name],
    )?;
    Ok(())
}

fn text(v: Option<&Value>) -> String {
    match v {
        Some(Value::String(s)) => s.clone(),
        Some(Value::Null) | None => String::new(),
        Some(other) => other.to_string(),
    }
}

fn title_of(row: &Map<String, Value>, spec: &Spec, name: &str) -> String {
    let title = text(row.get(&spec.title));
    if title.is_empty() {
        name.to_string()
    } else {
        title
    }
}

fn body_of(row: &Map<String, Value>, spec: &Spec, name: &str) -> String {
    let mut parts = vec![name.to_string()];
    parts.extend(spec.search.iter().map(|f| text(row.get(f))));
    parts.join(" ")
}

/// What was typed, as an FTS5 query: every word must match the start of a word, in any order.
fn match_expression(typed: &str) -> Option<String> {
    let words: Vec<String> = typed
        .split(|c: char| !c.is_alphanumeric())
        .filter(|w| !w.is_empty())
        .map(|w| format!("\"{w}\"*"))
        .collect();
    if words.is_empty() {
        None
    } else {
        Some(words.join(" "))
    }
}

fn sql_value(v: &Value) -> rusqlite::types::Value {
    use rusqlite::types::Value as Sql;
    match v {
        Value::Null => Sql::Null,
        Value::Bool(b) => Sql::Integer(*b as i64),
        Value::Number(n) => n
            .as_i64()
            .map(Sql::Integer)
            .unwrap_or_else(|| Sql::Real(n.as_f64().unwrap_or(0.0))),
        Value::String(s) => Sql::Text(s.clone()),
        other => Sql::Text(other.to_string()),
    }
}

#[cfg(test)]
mod outbox_tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn drafts_are_kept_per_user_and_survive_clearing_the_cache() {
        let s = Store::in_memory().unwrap();
        s.outbox_add(
            "a@x",
            "id-1",
            "Sales Invoice",
            &json!({"customer": "C"}),
            "C",
            1,
        )
        .unwrap();
        s.outbox_add("b@x", "id-2", "Quotation", &json!({}), "", 2)
            .unwrap();
        assert_eq!(s.outbox_list("a@x").unwrap().len(), 1);
        assert_eq!(s.outbox_list("b@x").unwrap()[0]["doctype"], "Quotation");
        s.forget_user().unwrap();
        assert_eq!(
            s.outbox_count("a@x").unwrap(),
            1,
            "a sign-in as someone else must not drop drafts"
        );
        // one user can neither change nor delete another's draft
        s.outbox_add(
            "b@x",
            "id-1",
            "Sales Invoice",
            &json!({"customer": "HIJACK"}),
            "",
            3,
        )
        .unwrap();
        assert_eq!(s.outbox_list("a@x").unwrap()[0]["doc"]["customer"], "C");
        s.outbox_delete("b@x", "id-1").unwrap();
        assert_eq!(s.outbox_count("a@x").unwrap(), 1);
    }

    #[test]
    fn a_failed_draft_keeps_its_reason_and_an_edit_makes_it_pending_again() {
        let s = Store::in_memory().unwrap();
        s.outbox_add("a@x", "id-1", "Sales Invoice", &json!({}), "", 1)
            .unwrap();
        s.outbox_mark("a@x", "id-1", "failed", Some("Customer is required"))
            .unwrap();
        assert_eq!(
            s.outbox_list("a@x").unwrap()[0]["error"],
            "Customer is required"
        );
        s.outbox_add(
            "a@x",
            "id-1",
            "Sales Invoice",
            &json!({"customer": "C"}),
            "C",
            1,
        )
        .unwrap();
        let d = &s.outbox_list("a@x").unwrap()[0];
        assert_eq!(
            (d["status"].as_str(), d["error"].is_null()),
            (Some("pending"), true)
        );
    }

    #[test]
    fn too_big_or_too_many_is_refused() {
        let s = Store::in_memory().unwrap();
        let big = json!({"notes": "x".repeat(OUTBOX_MAX_BYTES)});
        assert!(s
            .outbox_add("a@x", "big", "Sales Invoice", &big, "", 1)
            .is_err());
        for i in 0..OUTBOX_MAX {
            s.outbox_add("a@x", &format!("id-{i}"), "ToDo", &json!({}), "", i)
                .unwrap();
        }
        assert!(s
            .outbox_add("a@x", "one-more", "ToDo", &json!({}), "", 9999)
            .is_err());
    }

    #[test]
    fn another_user_doesnt_see_the_last_ones_answers() {
        let s = Store::in_memory().unwrap();
        s.set_kv("cache:home:x", "{\"cash\": 5}").unwrap();
        s.set_kv("cloud_sid", "secret").unwrap();
        s.set_kv("user", "a@x").unwrap();
        s.forget_user().unwrap();
        assert!(s.get_kv("cache:home:x").unwrap().is_none());
        assert!(s.get_kv("cloud_sid").unwrap().is_none());
    }
}
