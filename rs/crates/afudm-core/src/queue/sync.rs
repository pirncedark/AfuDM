//! Python manager._sync_aria2; callers serialize DB writes with Manager.kilit.
use super::*;

type Completed = Vec<(String, u64, String)>;

pub(super) fn collect(m: &Manager) -> Result<Completed> {
    let mut completed = crate::video::tamamlananlari_al(m);
    let rpc = m.rpc();
    if rpc.sleeping() {
        return Ok(completed);
    }
    let statuses = match (
        rpc.tell_active(&[]),
        rpc.tell_waiting(0, 200, &[]),
        rpc.tell_stopped(0, 100, &[]),
    ) {
        (Ok(mut active), Ok(waiting), Ok(stopped)) => {
            active.extend(waiting);
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
        // A stopped metadata GID may remain in aria2 long after its payload was attached.
        // Never let that metadata overwrite the payload row or its progress.
        if let Some(child) = status["followedBy"]
            .as_array()
            .and_then(|ids| ids.first())
            .and_then(Json::as_str)
            .filter(|id| !id.is_empty())
        {
            if m.store.by_gid(child)?.is_none() {
                let parent = match m.store.by_gid(gid)? {
                    Some(row) => Some(row),
                    None => shaping::matching_magnet(m, &status)?,
                };
                if let Some(row) =
                    parent.filter(|r| !matches!(text(&r["status"]), "removed" | "removing"))
                {
                    shaping::attach_payload(m, &row, child)?;
                }
            }
            continue;
        }
        let row = match m.store.by_gid(gid)? {
            Some(row) => Some(row),
            None => shaping::reattach(m, &status)?,
        };
        if row
            .as_ref()
            .is_some_and(|r| ["removing", "removed"].contains(&text(&r["status"])))
        {
            continue;
        }
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
            let mut fields = map(json!({"total_bytes":total,"done_bytes":done}));
            if matches!(status_name, "active" | "waiting") {
                fields.insert("error".into(), Json::Null);
            }
            if control_action(row).is_none() {
                fields.insert("status".into(), json!(status_name));
            }
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
                        "Dosya indirilemedi; tarayıcıdan yeniden indirin.",
                        gid,
                    );
                }
                let error = if html_error {
                    safety::HTML_ERROR.into()
                } else if safety::mega_expired(row, &status) {
                    safety::MEGA_EXPIRED_ERROR.into()
                } else if state(m)?.auth_required_gids.contains(gid) {
                    "Kaydedilen oturumdaki Cookie/Authorization guvenlik icin silindi. Yeni giris bilgileriyle indirmeyi Yenile.".into()
                } else {
                    shaping::engine_error(&status)
                        .chars()
                        .take(500)
                        .collect::<String>()
                };
                fields.insert("error".into(), json!(error));
                fields.insert("finished_at".into(), json!(now()));
            }
            if status_name == "complete" {
                if row["status"] != "complete" || !truthy(&row["finished_at"]) {
                    fields.insert("finished_at".into(), json!(now()));
                }
                state(m)?.cookies.remove(&row_id(row));
                clear_auth(m, gid)?;
            }
            let _guard = INTENT_LOCK.lock().unwrap_or_else(|e| e.into_inner());
            let Some(current) = m.store.by_gid(gid)? else {
                continue;
            };
            if matches!(text(&current["status"]), "removing" | "removed")
                || files::removal_failed(&current)
            {
                continue;
            }
            if control_action(&current).is_some() || current["status"] != row["status"] {
                fields.remove("status");
            }
            m.store.update_by_gid(gid, &fields)?;
        }
        if status_name == "complete"
            && !truthy(&status["followedBy"])
            && !state(m)?.known_complete.contains(gid)
        {
            if let Some(row) = &row {
                crate::torrent::secilmeyenleri_temizle(m, row, &status)?;
            }
            state(m)?.known_complete.insert(gid.into());
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
