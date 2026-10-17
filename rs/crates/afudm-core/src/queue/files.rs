//! File lookup and bounded removal, matching manager.py's orphan/parent handling.
use super::*;

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
    let _guard = m
        .kilit
        .lock()
        .map_err(|_| AfuError::Other("yonetici kilidi kullanilamiyor".into()))?;
    if !gid.is_empty() {
        state(m)?.removed_gids.insert(gid.into());
    }
    let row = record(m, gid)?;
    let live = m
        .rpc()
        .tell_status(gid, &["followedBy", "following", "files", "infoHash"])
        .ok();
    if row.is_none() && live.is_none() {
        return Ok(true);
    }
    let actual = row
        .as_ref()
        .map(|r| text(&r["gid"]))
        .filter(|s| !s.is_empty())
        .unwrap_or(gid);
    let mut gids = HashSet::from([actual.to_owned()]);
    let root = row
        .as_ref()
        .and_then(|r| r.get("dest_dir"))
        .and_then(Json::as_str)
        .filter(|s| !s.is_empty())
        .map(PathBuf::from)
        .unwrap_or(PathBuf::from(current_download_dir(m)?));
    let mut targets = Vec::new();
    if let Some(row) = &row {
        let hash = dosya_adi::magnet_hash(text(&row["source"]));
        if !hash.is_empty() {
            state(m)?.removed_hashes.insert(hash);
        }
    }
    if actual.starts_with("yt:") {
        let (job, stopper) = {
            let mut s = state(m)?;
            (s.video_jobs.remove(actual), s.video_stoppers.remove(actual))
        };
        if let Some(stop) = stopper {
            stop();
        }
        if let Some(job) = job {
            let dir = job
                .get("dest_dir")
                .or_else(|| job.get("dir"))
                .and_then(Json::as_str)
                .unwrap_or("");
            if !dir.is_empty() && !text(&job["filename"]).is_empty() {
                if let Some(path) = safe(
                    m,
                    Path::new(dir),
                    &Path::new(dir).join(text(&job["filename"])),
                    actual,
                ) {
                    targets.push(path);
                }
            }
        }
    } else {
        let live = if actual == gid {
            live
        } else {
            m.rpc().tell_status(actual, &[]).ok()
        };
        if let Some(status) = live {
            let hash = text(&status["infoHash"]).to_lowercase();
            if !hash.is_empty() {
                state(m)?.removed_hashes.insert(hash);
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
            }
        }
        for g in &gids {
            let _ = m.rpc().remove(g, true);
            let _ = m.rpc().remove_result(g);
        }
        let _ = m.rpc().save_session();
    }
    state(m)?.removed_gids.extend(gids);
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
        delete_targets(m, &root, &targets, actual);
    }
    if let Some(row) = &row {
        state(m)?.cookies.remove(&row_id(row));
        let _ = m.store.update_by_id(
            row_id(row),
            &map(json!({"status":"removed", "finished_at":now()})),
        );
    }
    clear_auth(m, actual)?;
    let _ = m.store.update_by_gid(
        actual,
        &map(json!({"status":"removed", "finished_at":now()})),
    );
    Ok(true)
}

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

pub(super) fn resolve(m: &Manager, gid: &str) -> Result<Option<PathBuf>> {
    let mut candidates = Vec::new();
    if let Ok(status) = m.rpc().tell_status(gid, &[]) {
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
        let dir = row
            .get("dest_dir")
            .filter(|v| truthy(v))
            .or_else(|| row.get("dir"))
            .and_then(Json::as_str)
            .unwrap_or("");
        if !dir.is_empty() && !text(&row["filename"]).is_empty() {
            let before = candidates.len();
            outputs(Path::new(dir), text(&row["filename"]), &mut candidates);
            if let Some(merged) = candidates.get(before).filter(|p| {
                p.is_file() && p.file_name().is_some_and(|n| n != text(&row["filename"]))
            }) {
                let _ = m.store.update_by_id(row_id(row), &map(json!({"filename":merged.file_name().map(|s|s.to_string_lossy()), "total_bytes":merged.metadata()?.len()})));
            }
        }
    }
    if let Some(job) = state(m)?.video_jobs.get(gid).cloned() {
        for key in ["output_path", "target_path"] {
            if !text(&job[key]).is_empty() {
                candidates.push(PathBuf::from(text(&job[key])));
            }
        }
        if !text(&job["dir"]).is_empty() && !text(&job["filename"]).is_empty() {
            outputs(
                Path::new(text(&job["dir"])),
                text(&job["filename"]),
                &mut candidates,
            );
        }
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
