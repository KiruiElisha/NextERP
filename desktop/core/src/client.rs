//! HTTP to the ERPNext site: sign in, keep Frappe's session cookie, call whitelisted methods.

use std::time::Duration;

use reqwest::{RequestBuilder, Response, StatusCode};
use serde_json::{Map, Value};

use crate::error::{Error, Result};

#[derive(Clone)]
pub struct Client {
    http: reqwest::Client,
    base: String,
    sid: Option<String>,
}

impl Client {
    /// `site` is the address as typed: "erp.example.com", "https://erp.example.com/", "http://localhost:8000".
    pub fn new(site: &str, sid: Option<String>) -> Result<Self> {
        let http = reqwest::Client::builder()
            .connect_timeout(Duration::from_secs(10))
            .timeout(Duration::from_secs(120))
            .build()?;
        Ok(Client {
            http,
            base: normalise(site),
            sid,
        })
    }

    pub fn base(&self) -> &str {
        &self.base
    }

    pub fn sid(&self) -> Option<&str> {
        self.sid.as_deref()
    }

    pub async fn login(&mut self, user: &str, password: &str) -> Result<()> {
        let res = self
            .http
            .post(format!("{}/api/method/login", self.base))
            .form(&[("usr", user), ("pwd", password)])
            .send()
            .await?;
        if res.status() == StatusCode::UNAUTHORIZED {
            return Err(Error::Server("Wrong email or password".into()));
        }
        let sid = res
            .headers()
            .get_all("set-cookie")
            .iter()
            .filter_map(|h| h.to_str().ok())
            .find_map(session_cookie);
        read(res).await?;
        self.sid =
            Some(sid.ok_or_else(|| Error::Server("The site did not start a session".into()))?);
        Ok(())
    }

    pub async fn logout(&mut self) {
        let _ = self.post("logout", &Value::Null).await;
        self.sid = None;
    }

    /// A write that may start a session (signing in with an emailed code): keeps the `sid` it sets.
    pub async fn post_keeping_session(&mut self, method: &str, args: &Value) -> Result<Value> {
        let res = self
            .http
            .post(self.url(method))
            .header("Accept", "application/json")
            .json(args)
            .send()
            .await?;
        if let Some(sid) = res
            .headers()
            .get_all("set-cookie")
            .iter()
            .filter_map(|h| h.to_str().ok())
            .find_map(session_cookie)
        {
            self.sid = Some(sid);
        }
        read(res).await
    }

    /// A read: arguments go in the query string, as Frappe expects for GET.
    pub async fn get(&self, method: &str, args: &Value) -> Result<Value> {
        let req = self.http.get(self.url(method)).query(&query_pairs(args));
        self.send(req).await
    }

    /// A write: arguments as a JSON body.
    pub async fn post(&self, method: &str, args: &Value) -> Result<Value> {
        let body = if args.is_null() {
            Value::Object(Map::new())
        } else {
            args.clone()
        };
        self.send(self.http.post(self.url(method)).json(&body))
            .await
    }

    async fn send(&self, req: RequestBuilder) -> Result<Value> {
        let req = req.header("Accept", "application/json");
        let req = match &self.sid {
            Some(sid) => req.header("Cookie", format!("sid={sid}")),
            None => req,
        };
        let res = req.send().await?;
        match res.status() {
            StatusCode::UNAUTHORIZED => Err(Error::SignedOut),
            // A guest is refused with the same 403 as a real permission error: ask who we are.
            StatusCode::FORBIDDEN if !self.signed_in().await => Err(Error::SignedOut),
            _ => read(res).await,
        }
    }

    async fn signed_in(&self) -> bool {
        let Some(sid) = &self.sid else { return false };
        let res = self
            .http
            .get(self.url("frappe.auth.get_logged_user"))
            .header("Cookie", format!("sid={sid}"))
            .send()
            .await;
        match res {
            Ok(r) if r.status().is_success() => r
                .json::<Value>()
                .await
                .map(|v| {
                    v.get("message")
                        .and_then(Value::as_str)
                        .is_some_and(|u| u != "Guest")
                })
                .unwrap_or(false),
            _ => false,
        }
    }

    fn url(&self, method: &str) -> String {
        format!("{}/api/method/{method}", self.base)
    }
}

/// The method's `message`, or the site's own words for why it refused.
async fn read(res: Response) -> Result<Value> {
    let ok = res.status().is_success();
    let body: Value = res.json().await.unwrap_or(Value::Null);
    if ok {
        return Ok(body.get("message").cloned().unwrap_or(Value::Null));
    }
    Err(Error::Server(server_message(&body)))
}

fn server_message(body: &Value) -> String {
    let from_messages = body
        .get("_server_messages")
        .and_then(Value::as_str)
        .and_then(|s| serde_json::from_str::<Vec<String>>(s).ok())
        .and_then(|list| list.into_iter().next())
        .map(|first| {
            serde_json::from_str::<Value>(&first)
                .ok()
                .and_then(|m| m.get("message").and_then(Value::as_str).map(str::to_string))
                .unwrap_or(first)
        });
    let text = from_messages
        .or_else(|| {
            body.get("exception")
                .and_then(Value::as_str)
                .map(str::to_string)
        })
        .unwrap_or_else(|| "The site refused the request".into());
    strip_tags(&text)
}

fn strip_tags(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut in_tag = false;
    for c in s.chars() {
        match c {
            '<' => in_tag = true,
            '>' => in_tag = false,
            _ if !in_tag => out.push(c),
            _ => {}
        }
    }
    out.trim().to_string()
}

/// The session id from one Set-Cookie header, unless it is the guest session.
fn session_cookie(header: &str) -> Option<String> {
    let value = header.split(';').next()?.trim().strip_prefix("sid=")?;
    (!value.is_empty() && value != "Guest").then(|| value.to_string())
}

fn query_pairs(args: &Value) -> Vec<(String, String)> {
    let Some(map) = args.as_object() else {
        return vec![];
    };
    map.iter()
        .filter(|(_, v)| !v.is_null())
        .map(|(k, v)| {
            (
                k.clone(),
                v.as_str()
                    .map(str::to_string)
                    .unwrap_or_else(|| v.to_string()),
            )
        })
        .collect()
}

fn normalise(site: &str) -> String {
    let site = site.trim().trim_end_matches('/');
    if site.starts_with("http://") || site.starts_with("https://") {
        site.to_string()
    } else {
        format!("https://{site}")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_bare_address_is_taken_as_https() {
        assert_eq!(normalise("erp.example.com/"), "https://erp.example.com");
        assert_eq!(normalise("http://localhost:8000"), "http://localhost:8000");
    }

    #[test]
    fn the_sites_own_message_is_shown_without_its_markup() {
        let body = serde_json::json!({"_server_messages": "[\"{\\\"message\\\": \\\"<b>Customer</b> is mandatory\\\"}\"]"});
        assert_eq!(server_message(&body), "Customer is mandatory");
    }

    #[test]
    fn the_session_comes_from_the_sid_cookie_and_never_the_guest_one() {
        assert_eq!(
            session_cookie("sid=abc123; Expires=Mon; Path=/").as_deref(),
            Some("abc123")
        );
        assert_eq!(session_cookie("sid=Guest; Path=/"), None);
        assert_eq!(session_cookie("system_user=yes; Path=/"), None);
    }

    #[test]
    fn get_arguments_that_are_not_text_are_sent_as_json() {
        let pairs = query_pairs(&serde_json::json!({"doctype": "Item", "limit": 5, "skip": null}));
        assert!(pairs.contains(&("doctype".into(), "Item".into())));
        assert!(pairs.contains(&("limit".into(), "5".into())));
        assert_eq!(pairs.len(), 2);
    }
}
