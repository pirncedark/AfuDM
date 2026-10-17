//! SAHIBI: Ekip G (codex). Bu dosyadaki govdeleri doldur; imzalari DEGISTIRME (afudm-types::ManagerApi).
#![allow(unused_variables)]

use crate::Manager;
#[allow(unused_imports)]
use afudm_types::{AfuError, Json, JsonMap, Result};
#[allow(unused_imports)]
use std::path::{Path, PathBuf};

/// Ekip G (codex) kendi calisma durumunu buraya koyar (Manager::butunluk_state).
#[derive(Default)]
pub struct State {}

pub fn butunluk_tara(m: &Manager, gid: &str) -> Result<Json> {
    let _ = m;
    todo!("butunluk_tara")
}

pub fn butunluk_onar(m: &Manager, gid: &str, yeni_url: &str) -> Result<Json> {
    let _ = m;
    todo!("butunluk_onar")
}

pub fn butunluk_hepsini_tara(m: &Manager) -> Result<Json> {
    let _ = m;
    todo!("butunluk_hepsini_tara")
}
