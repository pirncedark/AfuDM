//! One admission point for every interactive download source.
use afudm_types::{Json, JsonMap};
use serde_json::json;
use std::collections::BTreeMap;
use std::sync::mpsc;

pub fn now() -> f64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64()
}

pub struct Pending {
    pub request: JsonMap,
    reply: mpsc::Sender<Option<JsonMap>>,
}

#[derive(Default)]
pub struct PromptQueue {
    next: i64,
    pending: BTreeMap<i64, Pending>,
    suppressed: BTreeMap<String, f64>,
}

pub enum Admission {
    New(i64, mpsc::Receiver<Option<JsonMap>>),
    Duplicate(i64),
    Existing(Json),
}

pub fn normalized_url(raw: &str) -> String {
    match url::Url::parse(raw.trim()) {
        Ok(mut url) => {
            url.set_fragment(None);
            url.to_string()
        }
        Err(_) => raw.trim().to_owned(),
    }
}

fn key(req: &JsonMap) -> String {
    normalized_url(req.get("url").and_then(Json::as_str).unwrap_or(""))
}

pub fn existing_download(rows: &[Json], url: &str, now: f64) -> Option<Json> {
    let url = normalized_url(url);
    rows.iter()
        .find(|row| {
            normalized_url(row["source"].as_str().unwrap_or("")) == url
                && (matches!(
                    row["status"].as_str().unwrap_or(""),
                    "active" | "waiting" | "queued" | "scheduled" | "repairing" | "paused"
                ) || (row["status"] == "complete"
                    && row["finished_at"]
                        .as_f64()
                        .is_some_and(|at| now - at <= 300.0)))
        })
        .cloned()
}

impl PromptQueue {
    pub fn admit(&mut self, request: JsonMap, rows: &[Json], now: f64) -> Admission {
        self.suppressed.retain(|_, until| *until > now);
        let url = key(&request);
        if let Some(row) = existing_download(rows, &url, now) {
            return Admission::Existing(row);
        }
        if let Some((id, _)) = self.pending.iter().find(|(_, p)| key(&p.request) == url) {
            return Admission::Duplicate(*id);
        }
        if self.suppressed.contains_key(&url) {
            return Admission::Duplicate(0);
        }
        self.next += 1;
        let (reply, rx) = mpsc::channel();
        self.pending.insert(self.next, Pending { request, reply });
        Admission::New(self.next, rx)
    }

    pub fn list(&self) -> Vec<Json> {
        self.pending
            .iter()
            .map(|(id, pending)| {
                let mut item = pending.request.clone();
                item.insert("kimlik".into(), json!(id));
                Json::Object(item)
            })
            .collect()
    }

    pub fn approve(&mut self, id: i64, selection: JsonMap, now: f64) -> bool {
        let Some(pending) = self.pending.remove(&id) else {
            return false;
        };
        let url = key(&pending.request);
        // Cover the interval between approval and the manager persisting the job.
        self.suppressed.insert(url.clone(), now + 10.0);
        self.remove_copies(&url);
        let mut request = pending.request;
        request.extend(selection);
        pending.reply.send(Some(request)).is_ok()
    }

    fn remove_copies(&mut self, url: &str) {
        self.pending.retain(|_, p| {
            if key(&p.request) != url {
                return true;
            }
            let _ = p.reply.send(None);
            false
        });
    }

    pub fn cancel(&mut self, id: i64, now: f64) -> bool {
        let Some(pending) = self.pending.get(&id) else {
            return false;
        };
        let url = key(&pending.request);
        self.suppressed.insert(url.clone(), now + 120.0);
        self.remove_copies(&url);
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn req(url: &str) -> JsonMap {
        json!({"url":url}).as_object().unwrap().clone()
    }
    #[test]
    fn repeated_normalized_url_emits_only_one_dialog() {
        let mut q = PromptQueue::default();
        let Admission::New(id, _rx) = q.admit(req(" https://EXAMPLE.com:443/a#first "), &[], 0.0)
        else {
            panic!()
        };
        for _ in 0..10 {
            assert!(
                matches!(q.admit(req("https://example.com/a#second"), &[], 1.0), Admission::Duplicate(other) if other == id)
            );
        }
        assert_eq!(q.list().len(), 1);
        assert!(matches!(
            q.admit(req("https://example.com/a?token=other"), &[], 1.0),
            Admission::New(..)
        ));
    }
    #[test]
    fn active_queued_and_recent_complete_never_create_prompt() {
        for status in [
            "active",
            "queued",
            "waiting",
            "scheduled",
            "paused",
            "complete",
        ] {
            let mut q = PromptQueue::default();
            let rows =
                [json!({"source":"https://example.com/a", "status":status, "finished_at":900.0})];
            assert!(matches!(
                q.admit(req("https://example.com/a#part"), &rows, 1000.0),
                Admission::Existing(_)
            ));
            assert!(q.list().is_empty());
        }
        assert!(existing_download(
            &[json!({"source":"https://example.com/a","status":"complete","finished_at":1})],
            "https://example.com/a",
            1000.0
        )
        .is_none());
    }
    #[test]
    fn cancel_removes_all_copies_and_suppresses_for_two_minutes() {
        let mut q = PromptQueue::default();
        let Admission::New(id, rx) = q.admit(req("https://example.com/a"), &[], 0.0) else {
            panic!()
        };
        // Include a legacy duplicate already present before admission was fixed.
        let (tx, duplicate_rx) = mpsc::channel();
        q.pending.insert(
            99,
            Pending {
                request: req("https://example.com/a#copy"),
                reply: tx,
            },
        );
        assert!(q.cancel(id, 1.0));
        assert!(q.list().is_empty());
        assert!(rx.recv().unwrap().is_none());
        assert!(duplicate_rx.recv().unwrap().is_none());
        assert!(matches!(
            q.admit(req("https://example.com/a"), &[], 120.0),
            Admission::Duplicate(0)
        ));
        assert!(matches!(
            q.admit(req("https://example.com/a"), &[], 122.0),
            Admission::New(..)
        ));
    }
    #[test]
    fn approval_sends_one_reply_and_closes_admission_race() {
        let mut q = PromptQueue::default();
        let Admission::New(id, rx) = q.admit(req("https://example.com/a"), &[], 0.0) else {
            panic!()
        };
        assert!(q.approve(
            id,
            json!({"filename":"chosen.exe"})
                .as_object()
                .unwrap()
                .clone(),
            1.0
        ));
        assert_eq!(rx.recv().unwrap().unwrap()["filename"], "chosen.exe");
        assert!(!q.approve(id, JsonMap::new(), 1.0));
        assert!(matches!(
            q.admit(req("https://example.com/a"), &[], 2.0),
            Admission::Duplicate(0)
        ));
    }
}
