//! The desktop app's engine: a local cache of ERPNext data, the client that talks to the site, and
//! the sync between them. No UI here, so all of it is tested without a window.

pub mod client;
pub mod error;
pub mod store;
pub mod sync;

pub use client::Client;
pub use error::Error;
pub use store::{ListQuery, Store};
pub use sync::{Manifest, Spec};
