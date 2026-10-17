//! Portable SQLite storage and save-location backend.
#![recursion_limit = "256"]
pub mod kaydet;
pub mod paths;
mod schema;
pub mod settings;
mod store;
pub use store::SqliteStore;
#[cfg(test)]
mod tests;
