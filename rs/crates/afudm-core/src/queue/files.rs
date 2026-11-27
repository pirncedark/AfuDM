//! File lookup and bounded removal, matching manager.py's orphan/parent handling.
use super::*;
use std::sync::{Mutex, OnceLock};

static REMOVE_WORKERS: OnceLock<Mutex<HashSet<String>>> = OnceLock::new();

fn record(m: &Manager, gid: &str) -> Result<Option<Json>> {
    if let Some(id) = gid.strip_prefix("row:") {
        return match id.parse() {
            Ok(id) => m.store.by_id(id),
            Err(_) => Ok(None),
        };
    }
    m.store.by_gid(gid)
}

// Resolve existing ancestors too: a missing output may still have .aria2/.part siblings.
fn resolved(path: &Path) -> Option<PathBuf> {
    if let Ok(path) = path.canonicalize() {
        return Some(path);
    }
    if path.exists() || path.is_symlink() {
        return None;
    }
    let parent = resolved(path.parent()?)?;
    match path.file_name()?.to_str()? {
        "." => Some(parent),
        ".." => parent.parent().map(Path::to_path_buf),
        name => Some(parent.join(name)),
    }
}

fn safe(m: &Manager, root: &Path, candidate: &Path, gid: &str) -> Option<PathBuf> {
    let root = resolved(root)?;
    let candidate = resolved(candidate)?;
    if candidate != root && candidate.starts_with(&root) {
        return Some(candidate);
    }
    m.store
        .log("warn", "dosya indirme klasorunda degil, silinmedi", gid);
    None
}

pub(super) fn remove(m: &Manager, gid: &str, delete_files: bool) -> Result<bool> {
    let guard = INTENT_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let row = record(m, gid)?;
    if gid.starts_with("yt:") {
        let path = crate::video::kaldir(m, gid);
        if !gid.is_empty() {
            state(m)?.removed_gids.insert(gid.into());
        }
        if let Some(row) = &row {
            m.store.update_by_id(
                row_id(row),
                &map(json!({"status":"removed","finished_at":now()})),
            )?;
        }
        if delete_files {
            if let Some(path) = path {
                let root = path
                    .parent()
                    .map(Path::to_path_buf)
                    .or_else(|| row.as_ref().map(|r| PathBuf::from(text(&r["dest_dir"]))))
                    .unwrap_or_default();
                if let Some(path) = safe(m, &root, &path, gid) {
                    std::thread::spawn(move || {
                        while path.exists() {
                            erase(&path);
                            std::thread::sleep(Duration::from_millis(250));
                        }
                    });
                }
            }
        }
        return Ok(true);
    }
    if let Some(row) = &row {
        if row["status"] == "removed" {
            return Ok(true);
        }
        let mut opts = options(row);
        opts.remove("_afudm_pending_control");
        opts.insert("_afudm_remove_delete_files".into(), json!(delete_files));
        m.store.update_by_id(
            row_id(row),
            &map(json!({"status":"removing","finished_at":now(),"options":opts})),
        )?;
        state(m)?.cookies.remove(&row_id(row));
    }
    if !gid.is_empty() {
        state(m)?.removed_gids.insert(gid.into());
    }
    drop(guard);
    ensure_remove_worker(m, gid, delete_files);
    Ok(true)
}

fn worker_key(m: &Manager, gid: &str) -> String {
    format!("{}|{gid}", m.data_dir.display())
}

fn ensure_remove_worker(m: &Manager, gid: &str, delete_files: bool) {
    let key = worker_key(m, gid);
    let workers = REMOVE_WORKERS.get_or_init(|| Mutex::new(HashSet::new()));
    let Ok(mut active) = workers.lock() else {
        return;
    };
    if !active.insert(key.clone()) {
        return;
    }
    drop(active);
    let worker = background_manager(m);
    let gid = gid.to_owned();
    std::thread::spawn(move || {
        for attempt in 1..=WORKER_ATTEMPTS {
            let pending = record(&worker, &gid)
                .ok()
                .flatten()
                .is_some_and(|row| row["status"] == "removing");
            if !pending {
                break;
            }
            if remove_locked(&worker, &gid, delete_files).is_ok() {
                break;
            }
            if attempt == WORKER_ATTEMPTS {
                let message = "İndirme kaldırılamadı, tekrar deneyin.";
                if let Ok(Some(row)) = record(&worker, &gid) {
                    let _ = worker.store.update_by_id(
                        row_id(&row),
                        &map(json!({"status":"error","error":message})),
                    );
                    if let Ok(mut s) = state(&worker) {
                        s.removed_gids.remove(&gid);
                    }
                }
                worker.ui.notify("AfuDM", message);
                worker.store.log("error", message, &gid);
                break;
            }
            std::thread::sleep(Duration::from_millis(250));
        }
        if let Ok(mut set) = workers.lock() {
            set.remove(&key);
        }
    });
}

pub(super) fn removal_failed(row: &Json) -> bool {
    row["status"] == "error" && options(row).contains_key("_afudm_remove_delete_files")
}

pub(super) fn resume_pending(m: &Manager) {
    let Ok(rows) = m.store.list(Some("removing"), 1000) else {
        return;
    };
    for row in rows {
        let gid = text(&row["gid"]);
        if gid.is_empty() {
            continue;
        }
        let delete_files = options(&row)
            .get("_afudm_remove_delete_files")
            .and_then(Json::as_bool)
            .unwrap_or(false);
        ensure_remove_worker(m, gid, delete_files);
    }
}

fn remove_locked(m: &Manager, gid: &str, delete_files: bool) -> Result<bool> {
    if !gid.is_empty() {
        state(m)?.removed_gids.insert(gid.into());
    }
    let row = record(m, gid)?;
    let live = if gid.starts_with("row:") || gid.starts_with("yt:") || gid.starts_with("local:") {
        None
    } else {
        match m
            .rpc()
            .tell_status(gid, &["followedBy", "following", "files", "infoHash"])
        {
            Ok(status) => Some(status),
            Err(error) if rpc_not_found(&error) => None,
            Err(error) => return Err(error),
        }
    };
    if row.is_none() && live.is_none() {
        return Ok(true);
    }
    let actual = row
        .as_ref()
        .map(|r| text(&r["gid"]))
        .filter(|s| !s.is_empty())
        .unwrap_or(gid);
    let has_engine_job = !["row:", "local:", "yt:"]
        .iter()
        .any(|prefix| actual.starts_with(prefix));
    let mut gids = HashSet::from([actual.to_owned()]);
    let mut hashes = HashSet::new();
    let root = row
        .as_ref()
        .and_then(|r| r.get("dest_dir"))
        .and_then(Json::as_str)
        .filter(|s| !s.is_empty())
        .map(PathBuf::from)
        .unwrap_or(PathBuf::from(current_download_dir(m)?));
    let mut targets: Vec<PathBuf> = row
        .as_ref()
        .and_then(|r| options(r).get("_afudm_remove_targets").cloned())
        .and_then(|v| v.as_array().cloned())
        .unwrap_or_default()
        .iter()
        .filter_map(Json::as_str)
        .map(PathBuf::from)
        .collect();
    if let Some(row) = &row {
        let hash = dosya_adi::magnet_hash(text(&row["source"]));
        if !hash.is_empty() {
            hashes.insert(hash);
        }
    }
    if actual.starts_with("yt:") {
        // Python remove() yt dali: is durdurulur ve listeden atilir; hedef guvenli yolsa silinir.
        if let Some(path) = crate::video::kaldir(m, actual) {
            let root = path.parent().map(Path::to_path_buf).unwrap_or_default();
            if let Some(path) = safe(m, &root, &path, actual) {
                targets.push(path);
            }
        }
    } else if has_engine_job {
        let live = if actual == gid {
            live
        } else {
            m.rpc().tell_status(actual, &[]).ok()
        };
        if let Some(status) = live {
            let hash = text(&status["infoHash"]).to_lowercase();
            if !hash.is_empty() {
                hashes.insert(hash);
            }
            for child in status["followedBy"].as_array().into_iter().flatten() {
                if !text(child).is_empty() {
                    gids.insert(text(child).into());
                }
            }
            let parent = text(&status["following"]);
            if !parent.is_empty() {
                gids.insert(parent.into());
            }
            if delete_files {
                for g in &gids {
                    if let Ok(status) = m.rpc().tell_status(g, &["files"]) {
                        for entry in status["files"].as_array().into_iter().flatten() {
                            if !text(&entry["path"]).is_empty() {
                                if let Some(path) =
                                    safe(m, &root, Path::new(text(&entry["path"])), g)
                                {
                                    targets.push(path);
                                }
                            }
                        }
                    }
                }
                if let Some(row) = &row {
                    let mut opts = options(row);
                    opts.insert(
                        "_afudm_remove_targets".into(),
                        json!(targets
                            .iter()
                            .map(|p| p.to_string_lossy().to_string())
                            .collect::<Vec<_>>()),
                    );
                    m.store
                        .update_by_id(row_id(row), &map(json!({"options":opts})))?;
                }
            }
        }
        for g in &gids {
            if let Err(error) = m.rpc().remove(g, true) {
                if !rpc_not_found(&error) {
                    return Err(error);
                }
            }
            if let Err(error) = m.rpc().remove_result(g) {
                if !rpc_not_found(&error) {
                    return Err(error);
                }
            }
        }
        let _ = m.rpc().save_session();
    }
    if let Some(row) = &row {
        let opts = options(row);
        for raw in [
            &row["filename"],
            &row["title"],
            opts.get("filename").unwrap_or(&Json::Null),
            opts.get("title").unwrap_or(&Json::Null),
        ] {
            if !text(raw).is_empty() {
                if let Some(path) = safe(m, &root, &root.join(text(raw)), actual) {
                    targets.push(path);
                }
            }
        }
        if !text(&row["target_path"]).is_empty() {
            if let Some(path) = safe(m, &root, Path::new(text(&row["target_path"])), actual) {
                targets.push(path);
            }
        }
        let source = text(&row["source"]);
        if source.to_lowercase().ends_with(".torrent") {
            if let Some(path) = safe(m, &root, Path::new(source), actual).filter(|p| p.is_file()) {
                targets.push(path);
            }
        }
    }
    if delete_files {
        if let Some(row) = &row {
            let mut opts = options(row);
            opts.insert(
                "_afudm_remove_targets".into(),
                json!(targets
                    .iter()
                    .map(|p| p.to_string_lossy().to_string())
                    .collect::<Vec<_>>()),
            );
            m.store
                .update_by_id(row_id(row), &map(json!({"options":opts})))?;
        }
        delete_targets(m, &root, &targets, actual);
        if delete_targets_pending(m, &root, &targets, actual) {
            return Err(AfuError::Engine("indirme dosyasi halen kullanimda".into()));
        }
    }
    if let Some(row) = &row {
        state(m)?.cookies.remove(&row_id(row));
        m.store.update_by_id(
            row_id(row),
            &map(json!({"status":"removed", "finished_at":now()})),
        )?;
    }
    clear_auth(m, actual)?;
    m.store.update_by_gid(
        actual,
        &map(json!({"status":"removed", "finished_at":now()})),
    )?;
    let mut state = state(m)?;
    state.removed_gids.extend(gids);
    state.removed_hashes.extend(hashes);
    Ok(true)
}

pub(super) fn delete_targets_pending(
    m: &Manager,
    root: &Path,
    targets: &[PathBuf],
    gid: &str,
) -> bool {
    targets.iter().any(|target| {
        if target.exists() {
            return true;
        }
        let sidecar = PathBuf::from(format!("{}.aria2", target.to_string_lossy()));
        if safe(m, root, &sidecar, gid).is_some_and(|path| path.exists()) {
            return true;
        }
        let (Some(parent), Some(stem)) =
            (target.parent(), target.file_stem().and_then(|s| s.to_str()))
        else {
            return false;
        };
        std::fs::read_dir(parent).is_ok_and(|entries| {
            entries.flatten().any(|entry| {
                let path = entry.path();
                let name = entry.file_name().to_string_lossy().into_owned();
                path.is_file()
                    && name.starts_with(stem)
                    && ([".part", ".ytdl", ".temp", ".aria2"]
                        .iter()
                        .any(|suffix| name.ends_with(suffix))
                        || name.contains(".f"))
                    && safe(m, root, &path, gid).is_some_and(|path| path.exists())
            })
        })
    })
}

fn rpc_not_found(error: &AfuError) -> bool {
    let message = error.to_string().to_lowercase();
    message.contains("not found")
        || message.contains("notfound")
        || message.contains("does not exist")
}

// Windows'ta salt-okunur bayragini kaldirmak icin set_readonly(false) sart (Python'daki chmod karsiligi).
#[allow(clippy::permissions_set_readonly_false)]
fn erase(path: &Path) {
    for _ in 0..5 {
        if let Ok(meta) = path.symlink_metadata() {
            #[cfg(windows)]
            if meta.permissions().readonly() {
                let mut perms = meta.permissions();
                perms.set_readonly(false);
                let _ = std::fs::set_permissions(path, perms);
            }
            let result = if meta.is_dir() && !meta.is_symlink() {
                std::fs::remove_dir_all(path)
            } else {
                std::fs::remove_file(path)
            };
            if result.is_ok() {
                return;
            }
            std::thread::sleep(std::time::Duration::from_millis(100));
        } else {
            return;
        }
    }
}

fn delete_targets(m: &Manager, root: &Path, targets: &[PathBuf], gid: &str) {
    let mut seen = HashSet::new();
    for target in targets {
        let Some(target) = safe(m, root, target, gid) else {
            continue;
        };
        if !seen.insert(target.clone()) {
            continue;
        }
        let sidecar = PathBuf::from(format!("{}.aria2", target.to_string_lossy()));
        if let Some(path) = safe(m, root, &sidecar, gid) {
            erase(&path);
        }
        erase(&target);
        if let Some(path) = safe(m, root, &sidecar, gid) {
            erase(&path);
        }
        if let (Some(parent), Some(stem)) =
            (target.parent(), target.file_stem().and_then(|s| s.to_str()))
        {
            if let Ok(entries) = std::fs::read_dir(parent) {
                for entry in entries.flatten() {
                    let name = entry.file_name().to_string_lossy().into_owned();
                    if entry.path().is_file()
                        && name.starts_with(stem)
                        && ([".part", ".ytdl", ".temp", ".aria2"]
                            .iter()
                            .any(|s| name.ends_with(s))
                            || name.contains(".f"))
                    {
                        if let Some(path) = safe(m, root, &entry.path(), gid) {
                            erase(&path);
                        }
                    }
                }
            }
            if let Some(parent) = safe(m, root, parent, gid) {
                let _ = std::fs::remove_dir(parent);
            }
        }
    }
}

fn largest(path: &Path, seen: &mut HashSet<PathBuf>) -> Option<PathBuf> {
    if path.is_file() {
        return Some(path.to_path_buf());
    }
    if !seen.insert(path.canonicalize().ok()?) {
        return None;
    }
    std::fs::read_dir(path)
        .ok()?
        .flatten()
        .filter_map(|e| largest(&e.path(), seen))
        .max_by_key(|p| p.metadata().map(|m| m.len()).unwrap_or(0))
}

fn outputs(dir: &Path, filename: &str, candidates: &mut Vec<PathBuf>) {
    let path = dir.join(filename);
    // Prefer merged output to yt-dlp's intermediate *.fNNN.ext file.
    if let Some((stem, suffix)) = filename.rsplit_once(".f") {
        if let Some((format, ext)) = suffix.split_once('.') {
            if !format.is_empty() && format.chars().all(|c| c.is_ascii_digit()) {
                for ext in [ext, "mkv", "mp4", "webm"] {
                    let merged = dir.join(format!("{stem}.{ext}"));
                    if merged.is_file() {
                        candidates.push(merged);
                    }
                }
            }
        }
    }
    candidates.push(path);
    if let Ok(entries) = std::fs::read_dir(dir) {
        for entry in entries.flatten() {
            if entry.file_name().to_string_lossy().starts_with(filename) {
                candidates.push(entry.path());
            }
        }
    }
}

/// Python /dosya (telefona indir): once aria2 dosya yolu, sonra DB `path`.
pub(super) fn phone_path(m: &Manager, gid: &str) -> Result<Option<PathBuf>> {
    if let Ok(status) = m.rpc().tell_status(gid, &[]) {
        if let Some(path) = status["files"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(|f| f["path"].as_str())
            .find(|p| !p.is_empty())
        {
            return Ok(Some(PathBuf::from(path)));
        }
    }
    Ok(m.store.by_gid(gid)?.and_then(|r| {
        r["path"]
            .as_str()
            .filter(|p| !p.is_empty())
            .map(PathBuf::from)
    }))
}

pub(super) fn resolve(m: &Manager, gid: &str) -> Result<Option<PathBuf>> {
    let mut candidates = Vec::new();
    let status = if m.rpc().sleeping() {
        None
    } else {
        m.rpc().tell_status(gid, &[]).ok()
    };
    if let Some(status) = status {
        for file in status["files"].as_array().into_iter().flatten() {
            if !text(&file["path"]).is_empty() {
                candidates.push(PathBuf::from(text(&file["path"])));
            }
        }
    }
    let row = record(m, gid)?;
    if let Some(row) = &row {
        if !text(&row["target_path"]).is_empty() {
            candidates.push(PathBuf::from(text(&row["target_path"])));
        }
        if !text(&row["path"]).is_empty() {
            candidates.push(PathBuf::from(text(&row["path"])));
        }
        let dir = row
            .get("dest_dir")
            .filter(|v| truthy(v))
            .or_else(|| row.get("dir"))
            .and_then(Json::as_str)
            .unwrap_or("");
        if !dir.is_empty() && !text(&row["filename"]).is_empty() {
            let before = candidates.len();
            if row["kind"] == "video" {
                outputs(Path::new(dir), text(&row["filename"]), &mut candidates);
            } else {
                candidates.push(Path::new(dir).join(text(&row["filename"])));
            }
            if let Some(merged) = candidates
                .get(before)
                .filter(|p| p.file_name().is_some_and(|n| n != text(&row["filename"])))
            {
                if let Some(metadata) = merged.metadata().ok().filter(|m| m.is_file()) {
                    let _ = m.store.update_by_id(row_id(row), &map(json!({"filename":merged.file_name().map(|s|s.to_string_lossy()), "total_bytes":metadata.len()})));
                }
            }
        }
    }
    // Python resolve_item_path yt dali: video isinin hedef dosyasi (dest_dir + filename).
    if let Some(yol) = crate::video::dosya_yolu(m, gid) {
        if let (Some(dir), Some(ad)) = (yol.parent(), yol.file_name()) {
            outputs(dir, &ad.to_string_lossy(), &mut candidates);
        }
    }
    // Known output paths must never fall back to a default/category directory.
    // Keep a missing target too, so the shell can open its recorded parent.
    if !candidates.is_empty() {
        return Ok(candidates
            .iter()
            .find_map(|p| largest(p, &mut HashSet::new()))
            .or_else(|| candidates.first().cloned()));
    }
    if let Ok(snapshot) = shaping::snapshot(m) {
        for item in snapshot["items"].as_array().into_iter().flatten() {
            if item["gid"] == gid || row.as_ref().is_some_and(|r| r["id"] == item["id"]) {
                if !text(&item["target_path"]).is_empty() {
                    candidates.push(PathBuf::from(text(&item["target_path"])));
                }
                if !text(&item["filename"]).is_empty() {
                    let dir = item
                        .get("dir")
                        .filter(|v| truthy(v))
                        .and_then(Json::as_str)
                        .map(str::to_owned)
                        .unwrap_or(current_download_dir(m)?);
                    outputs(Path::new(&dir), text(&item["filename"]), &mut candidates);
                }
            }
        }
    }
    Ok(candidates
        .iter()
        .find_map(|p| largest(p, &mut HashSet::new())))
}
