//! Python manager._sync_aria2; callers serialize DB writes with Manager.kilit.
use super::*;

type Completed = Vec<(String, u64, String)>;

pub(super) fn collect(m: &Manager) -> Result<Completed> {
    let mut completed = crate::video::tamamlananlari_al(m);
    let rpc = m.rpc();
    if rpc.sleeping() {
        return Ok(completed);
    }
    let statuses = match (rpc.tell_active(&[]), rpc.tell_stopped(0, 100, &[])) {
        (Ok(mut active), Ok(stopped)) => {
            active.extend(stopped);
            active
        }
        _ => return Ok(completed),
    };
    shaping::track_previews(m, &statuses)?;
    let auth_error = regex::Regex::new(r"\b(?:401|403)\b").ok();
    for status in statuses {
        let gid = text(&status["gid"]);
        if gid.is_empty()
            || state(m)?.preview_gids.contains(gid)
            || state(m)?.removed_gids.contains(gid)
        {
            continue;
        }
        let row = match m.store.by_gid(gid)? {
            Some(row) => Some(row),
            None => shaping::reattach(m, &status)?,
        };
        let total = number(&status["totalLength"]);
        let done = number(&status["completedLength"]);
        let html_error = row
            .as_ref()
            .is_some_and(|r| status["status"] == "complete" && safety::html_error(r, &status));
        let status_name = if html_error {
            "error"
        } else {
            text(&status["status"])
        };
        let name = status["files"]
            .as_array()
            .and_then(|f| f.first())
            .and_then(|f| Path::new(text(&f["path"])).file_name())
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_default();
        if let Some(row) = &row {
            let mut fields =
                map(json!({"total_bytes":total,"done_bytes":done,"status":status_name}));
            if !name.is_empty() {
                fields.insert("filename".into(), json!(name));
            }
            if status_name == "error" {
                if !html_error && safety::retry_403(m, row, &status)? {
                    continue;
                }
                if row["kind"] == "http"
                    && row["status"] != "error"
                    && auth_error
                        .as_ref()
                        .is_some_and(|re| re.is_match(text(&status["errorMessage"])))
                {
                    m.store.log(
                        "warn",
                        "Görsel indirilemedi; tarayıcıdan yeniden indirin.",
                        gid,
                    );
                }
                let error = if html_error {
                    safety::HTML_ERROR.into()
                } else if state(m)?.auth_required_gids.contains(gid) {
                    "Kaydedilen oturumdaki Cookie/Authorization guvenlik icin silindi. Yeni giris bilgileriyle indirmeyi Yenile.".into()
                } else {
                    text(&status["errorMessage"])
                        .chars()
                        .take(500)
                        .collect::<String>()
                };
                fields.insert("error".into(), json!(error));
                fields.insert("finished_at".into(), json!(now()));
            }
            if status_name == "complete" {
                fields.insert("finished_at".into(), json!(now()));
                state(m)?.cookies.remove(&row_id(row));
                clear_auth(m, gid)?;
            }
            m.store.update_by_gid(gid, &fields)?;
        }
        let followed = status["followedBy"].as_array();
        if let (Some(child), Some(row)) = (followed.and_then(|a| a.first()), &row) {
            let child = text(child);
            if m.store.by_gid(child)?.is_none() {
                let has_selection = m.store.torrent_dosya_secimi_var(gid)?;
                let selection = m.store.torrent_dosya_secimleri(gid)?;
                m.store
                    .update_by_id(row_id(row), &map(json!({"gid":child,"status":"active"})))?;
                m.store.torrent_dosya_secimlerini_tasi(gid, child)?;
                if has_selection {
                    let value = if selection.is_empty() {
                        "0".into()
                    } else {
                        selection
                            .iter()
                            .map(ToString::to_string)
                            .collect::<Vec<_>>()
                            .join(",")
                    };
                    if let Err(e) = rpc.change_option(child, &map(json!({"select-file":value}))) {
                        m.store.log(
                            "warn",
                            &format!("magnet dosya secimi uygulanamadi: {e}"),
                            child,
                        );
                    }
                }
            }
        }
        if status_name == "complete"
            && !truthy(&status["followedBy"])
            && state(m)?.known_complete.insert(gid.into())
        {
            let title = if name.is_empty() {
                row.as_ref()
                    .map(|r| text(&r["title"]))
                    .filter(|s| !s.is_empty())
                    .unwrap_or(gid)
                    .to_owned()
            } else {
                name
            };
            completed.push((title, total as u64, gid.into()));
        }
    }
    Ok(completed)
}

pub(super) fn notify(m: &Manager, completed: Completed) {
    for (title, size, gid) in completed {
        tamamlandi(m, &title, size, &gid);
    }
}
