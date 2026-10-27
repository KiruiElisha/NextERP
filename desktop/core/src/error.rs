use serde::Serialize;

/// What went wrong, in the three ways the UI treats differently.
#[derive(Debug, thiserror::Error, Serialize)]
#[serde(tag = "kind", content = "message")]
pub enum Error {
    /// The session ended or was never there: show the sign-in screen.
    #[error("signed out")]
    SignedOut,
    /// The site answered with a refusal or a validation message, worth showing as it is.
    #[error("{0}")]
    Server(String),
    /// The site could not be reached; the cache still answers.
    #[error("cannot reach the site: {0}")]
    Network(String),
    #[error("local cache: {0}")]
    Cache(String),
}

impl From<rusqlite::Error> for Error {
    fn from(e: rusqlite::Error) -> Self {
        Error::Cache(e.to_string())
    }
}

impl From<reqwest::Error> for Error {
    fn from(e: reqwest::Error) -> Self {
        Error::Network(e.to_string())
    }
}

pub type Result<T> = std::result::Result<T, Error>;
