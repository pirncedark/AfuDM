//! SAHIBI: Ekip D (claude kod ajani). Bu dosyadaki govdeleri doldur; imzalari DEGISTIRME (afudm-types::ManagerApi).
#![allow(unused_variables)]

use crate::Manager;
#[allow(unused_imports)]
use afudm_types::{AfuError, Json, JsonMap, Result};
#[allow(unused_imports)]
use std::path::{Path, PathBuf};

/// Ekip D (claude kod ajani) kendi calisma durumunu buraya koyar (Manager::video_state).
#[derive(Default)]
pub struct State {}

pub fn probe_video(m: &Manager, url: &str) -> Result<Json> {
    let _ = m;
    todo!("probe_video")
}
