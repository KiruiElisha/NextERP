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
";

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
