use super::*;

fn rounded(value: f64, digits: i32) -> f64 {
    let scale = 10f64.powi(digits);
    (value * scale).round_ties_even() / scale
}

pub(super) fn aria(m: &Manager, status: &Json) -> Result<Json> {
    let gid = text(&status["gid"]);
    let row = m.store.by_gid(gid)?.unwrap_or(Json::Null);
    let total = number(&status["totalLength"]);
    let done = number(&status["completedLength"]);
    let speed = number(&status["downloadSpeed"]);
    let name = status["files"]
        .as_array()
        .and_then(|f| f.first())
        .map(|f| {
            Path::new(text(&f["path"]))
                .file_name()
                .map(|n| n.to_string_lossy().into_owned())
                .unwrap_or_default()
        })
        .unwrap_or_default();
    let torrent = truthy(&status["bittorrent"]) || truthy(&status["infoHash"]);
    let title = [
        text(&status["bittorrent"]["info"]["name"]),
        &name,
        text(&row["title"]),
        gid,
    ]
    .into_iter()
    .find(|s| !s.is_empty())
    .unwrap_or("");
    let title = title.strip_prefix("[METADATA]").unwrap_or(title);
    let started = row["started_at"].as_f64().unwrap_or(0.0);
    let elapsed = if started != 0.0 {
        (now() - started).max(1.0)
    } else {
        0.0
    };
    let auth = state(m)?.auth_required_gids.contains(gid);
    let error = if auth {
        "Kaydedilen oturumdaki Cookie/Authorization güvenlik için silindi. Yeni giriş bilgileriyle indirmeyi Yenile."
    } else {
        [text(&status["errorMessage"]), text(&row["error"])]
            .into_iter()
            .find(|s| !s.is_empty())
            .unwrap_or("")
    };
    let mut item = map(
        json!({"id":row.get("id"),"gid":gid,"kind":if torrent{"torrent"}else{row.get("kind").and_then(Json::as_str).unwrap_or("http")},"status":if auth{"error"}else{status.get("status").and_then(Json::as_str).unwrap_or("unknown")},"title":title,"filename":name,"totalLength":total,"completedLength":done,"progress":if total!=0{rounded(done as f64/total as f64*100.0,1)}else{0.0},"downloadSpeed":speed,"avgSpeed":if elapsed>0.0 && done!=0{(done as f64/elapsed) as i64}else{0},"elapsed":elapsed as i64,"remaining":(total-done).max(0),"uploadSpeed":number(&status["uploadSpeed"]),"connections":number(&status["connections"]),"numSeeders":number(&status["numSeeders"]),"seeder":status["seeder"]=="true","eta":if speed>0 && total>done{(total-done)/speed}else{0},"dir":status.get("dir").cloned().unwrap_or(json!("")),"errorMessage":error,"infoHash":status.get("infoHash").cloned().unwrap_or(json!("")),"numPieces":number(&status["numPieces"]),"source":row.get("source").cloned().unwrap_or(json!("")),"uploadLength":number(&status["uploadLength"]),"ratio":if done!=0{rounded(number(&status["uploadLength"]) as f64/done as f64,3)}else{0.0}}),
    );
    if torrent {
        item.extend(crate::torrent::snapshot_alanlari(m, status));
    }
    Ok(json!(item))
}

pub(super) fn row(row: &Json) -> Json {
    let total = number(&row["total_bytes"]);
    let done = number(&row["done_bytes"]);
    let mut progress = if total != 0 {
        rounded(done as f64 / total as f64 * 100.0, 1)
    } else {
        0.0
    };
    let mut error = text(&row["error"]).to_owned();
    if row["status"] == "repairing" {
        let opts = options(row);
        let rep = opts.get("repair_state").unwrap_or(&Json::Null);
        if truthy(rep) {
            let total = rep.get("toplam_blok").map(number).unwrap_or(1);
            progress = if total != 0 {
                rounded(number(&rep["duzeltilen"]) as f64 / total as f64 * 100.0, 1)
            } else {
                0.0
            };
            if truthy(&rep["hata"]) {
                error = text(&rep["hata"]).into();
            }
        }
    }
    json!({"id":row["id"],"gid":row.get("gid").filter(|v|truthy(v)).cloned().unwrap_or(json!(format!("row:{}",row_id(row)))),"kind":row["kind"],"status":row["status"],"title":row.get("title").filter(|v|truthy(v)).cloned().unwrap_or_else(||row["source"].clone()),"filename":row.get("filename").filter(|v|truthy(v)).cloned().unwrap_or(json!("")),"totalLength":total,"completedLength":done,"progress":progress,"downloadSpeed":0,"uploadSpeed":0,"connections":0,"numSeeders":0,"eta":0,"dir":row.get("dest_dir").filter(|v|truthy(v)).cloned().unwrap_or(json!("")),"errorMessage":error,"source":row["source"],"start_after":row["start_after"]})
}

pub(super) fn reattach(m: &Manager, status: &Json) -> Result<Option<Json>> {
    let gid = text(&status["gid"]);
    if state(m)?.preview_gids.contains(gid) {
        return Ok(None);
    }
    if let Some(parent) = m.store.by_gid(text(&status["following"]))? {
        m.store
            .update_by_id(row_id(&parent), &map(json!({"gid":gid})))?;
        m.store
            .torrent_dosya_secimlerini_tasi(text(&parent["gid"]), gid)?;
        return m.store.by_id(row_id(&parent));
    }
    let hash = text(&status["infoHash"]).to_lowercase();
    if hash.is_empty() {
        return Ok(None);
    }
    for row in m.store.list(None, 300)? {
        if row["kind"] == "torrent"
            && ACTIVE.contains(&text(&row["status"]))
            && dosya_adi::magnet_hash(text(&row["source"])) == hash
        {
            m.store
                .update_by_id(row_id(&row), &map(json!({"gid":gid})))?;
            m.store.log(
                "info",
                &format!("torrent kaydi yeniden baglandi: {}", text(&row["title"])),
                gid,
            );
            return m.store.by_id(row_id(&row));
        }
    }
    Ok(None)
}

pub(super) fn snapshot(m: &Manager) -> Result<Json> {
    let live = {
        let _guard = m
            .kilit
            .lock()
            .map_err(|_| AfuError::Other("yonetici kilidi kullanilamiyor".into()))?;
        match live_statuses(m) {
            Ok(live) => {
                track_previews(m, &live)?;
                live
            }
            Err(_) => {
                state(m)?.last_error = "motor durum bilgisi alinamadi".into();
                vec![]
            }
        }
    };
    let mut items = Vec::new();
    let mut gids = HashSet::new();
    let mut ids = HashSet::new();
    for status in live {
        let gid = text(&status["gid"]);
        {
            let s = state(m)?;
            if gid.is_empty()
                || s.removed_gids.contains(gid)
                || s.preview_gids.contains(gid)
                || truthy(&status["followedBy"])
            {
                continue;
            }
        }
        let row = m.store.by_gid(gid)?;
        let hash = text(&status["infoHash"]).to_lowercase();
        if !hash.is_empty() && state(m)?.removed_hashes.contains(&hash) && row.is_none() {
            continue;
        }
        if row.as_ref().is_some_and(|r| r["status"] == "removed") {
            state(m)?.removed_gids.insert(gid.into());
            continue;
        }
        if row.as_ref().is_some_and(|r| r["status"] == "removed") {
            state(m)?.removed_gids.insert(gid.into());
            continue;
        }
        gids.insert(gid.to_owned());
        if let Some(r) = row {
            ids.insert(row_id(&r));
        }
        let shaped = aria(m, &status)?;
        items.push(shaped);
    }
    let jobs = crate::video::video_satirlari(m);
    for job in &jobs {
        let gid = text(&job["gid"]).to_owned();
        if state(m)?.removed_gids.contains(&gid) || job["status"] == "removed" {
            continue;
        }
        let row = m.store.by_gid(&gid)?;
        if row.as_ref().is_some_and(|r| r["status"] == "removed") {
            state(m)?.removed_gids.insert(gid.clone());
            continue;
        }
        let mut shaped = job.clone();
        shaped["id"] = row
            .as_ref()
            .and_then(|r| r.get("id"))
            .cloned()
            .unwrap_or(Json::Null);
        let total = number(&job["totalLength"]);
        let done = number(&job["completedLength"]);
        shaped["progress"] = json!(if total != 0 {
            rounded(done as f64 / total as f64 * 100.0, 1)
        } else {
            0.0
        });
        gids.insert(gid.clone());
        if let Some(row) = row {
            ids.insert(row_id(&row));
        }
        items.push(shaped);
    }
    for record in m.store.list(None, 200)? {
        if ids.contains(&row_id(&record)) || record["status"] == "removed" {
            continue;
        }
        let gid = text(&record["gid"]);
        if !gid.is_empty() && (gids.contains(gid) || state(m)?.removed_gids.contains(gid)) {
            continue;
        }
        let hash = dosya_adi::magnet_hash(text(&record["source"]));
        if !hash.is_empty() && state(m)?.removed_hashes.contains(&hash) {
            continue;
        }
        if ["complete", "error", "scheduled", "paused", "repairing"]
            .contains(&text(&record["status"]))
        {
            items.push(row(&record));
        }
    }
    let stat = m.rpc().global_stat().unwrap_or(json!({}));
    let lang = language(text(&setting(m, "language", json!("auto"))?));
    Ok(
        json!({"items":items,"stat":{"downloadSpeed":number(&stat["downloadSpeed"])+crate::video::hiz_toplami(m) as i64,"uploadSpeed":number(&stat["uploadSpeed"]),"numActive":number(&stat["numActive"])+crate::video::aktif_sayisi(m) as i64,"numWaiting":number(&stat["numWaiting"]),"numStopped":number(&stat["numStopped"])},"settings":m.store.all_settings()?,"engine_ok":m.rpc().alive(),"download_dir":current_download_dir(m)?,"lang":lang,"last_error":state(m)?.last_error,"automation":m.store.automation_jobs("",200)?}),
    )
}

pub(super) fn track_previews(m: &Manager, live: &[Json]) -> Result<()> {
    let mut previews = state(m)?.preview_gids.clone();
    loop {
        let before = previews.len();
        for s in live {
            if previews.contains(text(&s["following"])) && !text(&s["gid"]).is_empty() {
                previews.insert(text(&s["gid"]).into());
            }
            if previews.contains(text(&s["gid"])) {
                for child in s["followedBy"].as_array().into_iter().flatten() {
                    if !text(child).is_empty() {
                        previews.insert(text(child).into());
                    }
                }
            }
        }
        if before == previews.len() {
            break;
        }
    }
    state(m)?.preview_gids = previews;
    Ok(())
}

pub(super) fn language(selected: &str) -> String {
    let selected = selected.trim().to_lowercase();
    if ["en", "tr"].contains(&selected.as_str()) {
        return selected;
    }
    #[cfg(windows)]
    {
        #[link(name = "kernel32")]
        extern "system" {
            fn GetUserDefaultUILanguage() -> u16;
        }
        // SAFETY: no pointers/arguments; Win32 returns the calling user's language ID.
        if unsafe { GetUserDefaultUILanguage() } & 0x3ff == 0x1f {
            return "tr".into();
        }
    }
    #[cfg(not(windows))]
    if std::env::var("LANG").is_ok_and(|s| s.to_lowercase().starts_with("tr")) {
        return "tr".into();
    }
    "en".into()
}
