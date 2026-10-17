//! Thread-safe Python Store implementation.
use afudm_types::{AfuError, Json, JsonMap, Result, Store};
use rusqlite::{
    params, params_from_iter,
    types::{Value, ValueRef},
    Connection,
};
use serde_json::json;
use std::{
    path::Path,
    sync::{Mutex, MutexGuard},
    time::{Duration, SystemTime, UNIX_EPOCH},
};

pub struct SqliteStore {
    conn: Mutex<Connection>,
}
fn db_error(_: rusqlite::Error) -> AfuError {
    AfuError::Db("Veritabani islemi basarisiz.".into())
}
pub(crate) fn now() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0.0, |d| d.as_secs_f64())
}
pub(crate) fn truthy(v: &Json) -> bool {
    match v {
        Json::Null => false,
        Json::Bool(v) => *v,
        Json::Number(n) => n.as_f64() != Some(0.0),
        Json::String(s) => !s.is_empty(),
        Json::Array(a) => !a.is_empty(),
        Json::Object(o) => !o.is_empty(),
    }
}
fn sql_value(v: &Json) -> Value {
    match v {
        Json::Null => Value::Null,
        Json::Bool(b) => Value::Integer(i64::from(*b)),
        Json::Number(n) => n
            .as_i64()
            .map(Value::Integer)
            .or_else(|| n.as_f64().map(Value::Real))
            .unwrap_or(Value::Null),
        Json::String(s) => Value::Text(s.clone()),
        _ => Value::Text(v.to_string()),
    }
}
fn query_conn(conn: &Connection, sql: &str, args: &[Json]) -> Result<Vec<Json>> {
    let mut stmt = conn.prepare(sql).map_err(db_error)?;
    let names: Vec<String> = stmt.column_names().into_iter().map(str::to_owned).collect();
    let values: Vec<Value> = args.iter().map(sql_value).collect();
    let mut rows = stmt.query(params_from_iter(values)).map_err(db_error)?;
    let mut out = Vec::new();
    while let Some(row) = rows.next().map_err(db_error)? {
        let mut obj = JsonMap::new();
        for (i, name) in names.iter().enumerate() {
            let value = match row.get_ref(i).map_err(db_error)? {
                ValueRef::Null => Json::Null,
                ValueRef::Integer(n) => json!(n),
                ValueRef::Real(n) => json!(n),
                ValueRef::Text(s) => json!(String::from_utf8_lossy(s)),
                ValueRef::Blob(b) => json!(b),
            };
            obj.insert(name.clone(), value);
        }
        out.push(Json::Object(obj));
    }
    Ok(out)
}
fn decode(row: &mut Json, key: &str, fallback: Json) {
    row[key] = row
        .get(key)
        .and_then(Json::as_str)
        .and_then(|s| serde_json::from_str::<Json>(s).ok())
        .filter(|v| !v.is_null())
        .unwrap_or(fallback);
}
fn downloads(mut rows: Vec<Json>) -> Vec<Json> {
    for r in &mut rows {
        decode(r, "options", json!({}));
    }
    rows
}
fn jobs(mut rows: Vec<Json>) -> Vec<Json> {
    for r in &mut rows {
        decode(r, "payload", json!({}));
    }
    rows
}
fn plugins(mut rows: Vec<Json>) -> Vec<Json> {
    for r in &mut rows {
        for (key, empty) in [
            ("manifest", json!({})),
            ("izinler", json!([])),
            ("domainler", json!([])),
            ("ayarlar", json!({})),
        ] {
            decode(r, key, empty);
        }
        r["etkin"] = json!(truthy(&r["etkin"]));
    }
    rows
}
fn quoted(s: &str) -> String {
    format!("\"{}\"", s.replace('"', "\"\""))
}
impl SqliteStore {
    pub fn open(path: &Path) -> Result<Self> {
        Self::init(Connection::open(path).map_err(db_error)?)
    }
    pub fn open_in_memory() -> Result<Self> {
        Self::init(Connection::open_in_memory().map_err(db_error)?)
    }
    fn init(mut conn: Connection) -> Result<Self> {
        conn.busy_timeout(Duration::from_secs(15))
            .map_err(db_error)?;
        conn.pragma_update(None, "journal_mode", "WAL")
            .map_err(db_error)?;
        conn.execute_batch(crate::schema::BASE).map_err(db_error)?;
        {
            let tx = conn.transaction().map_err(db_error)?;
            for (k, v) in crate::settings::default_settings() {
                tx.execute(
                    "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
                    params![k, v.to_string()],
                )
                .map_err(db_error)?;
            }
            tx.commit().map_err(db_error)?;
        }
        crate::schema::migrate(&mut conn).map_err(db_error)?;
        let store = Self {
            conn: Mutex::new(conn),
        };
        if !store
            .get("auto_accept_migrated")?
            .as_ref()
            .is_some_and(truthy)
        {
            let mut conn = store.lock()?;
            let tx = conn.transaction().map_err(db_error)?;
            tx.execute(
                "UPDATE settings SET value='false' WHERE key='kaydetme_penceresi'",
                [],
            )
            .map_err(db_error)?;
            tx.execute(
                "INSERT OR REPLACE INTO settings(key,value) VALUES('auto_accept_migrated','true')",
                [],
            )
            .map_err(db_error)?;
            tx.commit().map_err(db_error)?;
        }
        Ok(store)
    }
    fn lock(&self) -> Result<MutexGuard<'_, Connection>> {
        self.conn
            .lock()
            .map_err(|_| AfuError::Db("Veritabani kilidi kullanilamiyor.".into()))
    }
    fn update(&self, table: &str, field: &str, id: Json, fields: &JsonMap) -> Result<()> {
        if fields.is_empty() {
            return Ok(());
        }
        let cols = fields
            .keys()
            .map(|k| format!("{}=?", quoted(k)))
            .collect::<Vec<_>>()
            .join(",");
        let mut args: Vec<Json> = fields.values().cloned().collect();
        args.push(id);
        self.execute(&format!("UPDATE {table} SET {cols} WHERE {field}=?"), &args)?;
        Ok(())
    }
}
impl Store for SqliteStore {
    fn query(&self, sql: &str, params: &[Json]) -> Result<Vec<Json>> {
        let conn = self.lock()?;
        query_conn(&conn, sql, params)
    }
    fn execute(&self, sql: &str, args: &[Json]) -> Result<usize> {
        let values: Vec<_> = args.iter().map(sql_value).collect();
        self.lock()?
            .execute(sql, params_from_iter(values))
            .map_err(db_error)
    }
    fn get(&self, key: &str) -> Result<Option<Json>> {
        let rows = self.query("SELECT value FROM settings WHERE key=?", &[json!(key)])?;
        Ok(rows
            .first()
            .map(|r| {
                r["value"]
                    .as_str()
                    .map(|s| serde_json::from_str(s).unwrap_or_else(|_| json!(s)))
                    .unwrap_or(Json::Null)
            })
            .or_else(|| crate::settings::default_settings().remove(key)))
    }
    fn set(&self, key: &str, value: Json) -> Result<()> {
        self.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", &[json!(key),json!(value.to_string())])?;
        Ok(())
    }
    fn all_settings(&self) -> Result<JsonMap> {
        let mut out = crate::settings::default_settings();
        for r in self.query("SELECT key,value FROM settings", &[])? {
            if let Some(k) = r["key"].as_str() {
                out.insert(
                    k.into(),
                    r["value"]
                        .as_str()
                        .map(|s| serde_json::from_str(s).unwrap_or_else(|_| json!(s)))
                        .unwrap_or(Json::Null),
                );
            }
        }
        Ok(out)
    }
    fn rules_list(&self) -> Result<Vec<Json>> {
        let mut rows = self.query("SELECT * FROM rules ORDER BY priority,id", &[])?;
        for r in &mut rows {
            r["active"] = json!(truthy(&r["active"]));
            for k in ["conditions", "actions"] {
                r[k] = serde_json::from_str(r[k].as_str().unwrap_or(""))
                    .map_err(|_| AfuError::Db("Gecersiz kural JSON kaydi.".into()))?;
            }
        }
        Ok(rows)
    }
    fn rules_save(&self, rules: &[Json]) -> Result<()> {
        let mut conn = self.lock()?;
        let tx = conn.transaction().map_err(db_error)?;
        tx.execute("DELETE FROM rules", []).map_err(db_error)?;
        for (i, r) in rules.iter().enumerate() {
            let id = r.get("id").ok_or_else(|| AfuError::Invalid("id".into()))?;
            let name = r
                .get("name")
                .ok_or_else(|| AfuError::Invalid("name".into()))?;
            let args = [
                id.clone(),
                name.clone(),
                json!(r.get("active").is_none_or(truthy)),
                json!(i + 1),
                r.get("match_type").cloned().unwrap_or(json!("all")),
                json!(r
                    .get("conditions")
                    .filter(|v| truthy(v))
                    .cloned()
                    .unwrap_or(json!([]))
                    .to_string()),
                json!(r
                    .get("actions")
                    .filter(|v| truthy(v))
                    .cloned()
                    .unwrap_or(json!({}))
                    .to_string()),
            ];
            tx.execute("INSERT INTO rules(id,name,active,priority,match_type,conditions,actions) VALUES(?,?,?,?,?,?,?)",params_from_iter(args.iter().map(sql_value))).map_err(db_error)?;
        }
        tx.commit().map_err(db_error)
    }
    fn add(
        &self,
        kind: &str,
        source: &str,
        title: Option<&str>,
        dest_dir: Option<&str>,
        options: Option<&JsonMap>,
        start_after: Option<f64>,
        gid: Option<&str>,
    ) -> Result<i64> {
        let conn = self.lock()?;
        conn.execute("INSERT INTO downloads(gid,kind,source,title,dest_dir,options,added_at,start_after,status) VALUES(?,?,?,?,?,?,?,?,?)",params![gid,kind,source,title,dest_dir,json!(options.cloned().unwrap_or_default()).to_string(),now(),start_after,if start_after.is_some_and(|s|s!=0.0) {"scheduled"} else {"queued"}]).map_err(db_error)?;
        Ok(conn.last_insert_rowid())
    }
    fn attach_gid(&self, row_id: i64, gid: &str) -> Result<()> {
        self.execute(
            "UPDATE downloads SET gid=?,status='active',started_at=? WHERE id=?",
            &[json!(gid), json!(now()), json!(row_id)],
        )?;
        Ok(())
    }
    fn update_by_gid(&self, gid: &str, fields: &JsonMap) -> Result<()> {
        self.update("downloads", "gid", json!(gid), fields)
    }
    fn update_by_id(&self, row_id: i64, fields: &JsonMap) -> Result<()> {
        self.update("downloads", "id", json!(row_id), fields)
    }
    fn by_gid(&self, gid: &str) -> Result<Option<Json>> {
        Ok(downloads(self.query("SELECT * FROM downloads WHERE gid=?", &[json!(gid)])?).pop())
    }
    fn by_id(&self, row_id: i64) -> Result<Option<Json>> {
        Ok(downloads(self.query("SELECT * FROM downloads WHERE id=?", &[json!(row_id)])?).pop())
    }
    fn list(&self, status: Option<&str>, limit: usize) -> Result<Vec<Json>> {
        let (sql, args) = match status.filter(|s| !s.is_empty()) {
            Some(s) => (
                "SELECT * FROM downloads WHERE status=? ORDER BY added_at DESC LIMIT ?",
                vec![json!(s), json!(limit)],
            ),
            None => (
                "SELECT * FROM downloads ORDER BY added_at DESC LIMIT ?",
                vec![json!(limit)],
            ),
        };
        Ok(downloads(self.query(sql, &args)?))
    }
    fn max_video_seq(&self) -> Result<i64> {
        Ok(self
            .query("SELECT gid FROM downloads WHERE gid LIKE 'yt:%'", &[])?
            .iter()
            .filter_map(|r| {
                r["gid"]
                    .as_str()?
                    .split_once(':')?
                    .1
                    .trim()
                    .parse::<i64>()
                    .ok()
            })
            .max()
            .unwrap_or(0)
            .max(0))
    }
    fn torrent_dosya_secimlerini_kaydet(&self, gid: &str, indeksler: &[i64]) -> Result<()> {
        let mut conn = self.lock()?;
        let tx = conn.transaction().map_err(db_error)?;
        tx.execute("DELETE FROM torrent_file_selections WHERE gid=?", [gid])
            .map_err(db_error)?;
        tx.execute(
            "INSERT INTO torrent_file_selections(gid,file_index,selected) VALUES(?,0,1)",
            [gid],
        )
        .map_err(db_error)?;
        let indices: std::collections::BTreeSet<_> = indeksler.iter().collect();
        for i in indices {
            tx.execute(
                "INSERT INTO torrent_file_selections(gid,file_index,selected) VALUES(?,?,1)",
                params![gid, i],
            )
            .map_err(db_error)?;
        }
        tx.commit().map_err(db_error)
    }
    fn torrent_dosya_secimleri(&self, gid: &str) -> Result<Vec<i64>> {
        Ok(self.query("SELECT file_index FROM torrent_file_selections WHERE gid=? AND file_index>0 AND selected=1 ORDER BY file_index",&[json!(gid)])?.iter().filter_map(|r|r["file_index"].as_i64()).collect())
    }
    fn torrent_dosya_secimi_var(&self, gid: &str) -> Result<bool> {
        Ok(!self
            .query(
                "SELECT 1 FROM torrent_file_selections WHERE gid=? AND file_index=0",
                &[json!(gid)],
            )?
            .is_empty())
    }
    fn torrent_dosya_secimlerini_tasi(&self, eski_gid: &str, yeni_gid: &str) -> Result<()> {
        self.execute(
            "UPDATE OR IGNORE torrent_file_selections SET gid=? WHERE gid=?",
            &[json!(yeni_gid), json!(eski_gid)],
        )?;
        Ok(())
    }
    fn due_scheduled(&self, time: Option<f64>) -> Result<Vec<Json>> {
        Ok(downloads(self.query("SELECT * FROM downloads WHERE status='scheduled' AND start_after IS NOT NULL AND start_after<=?",&[json!(time.filter(|v|*v!=0.0).unwrap_or_else(now))])?))
    }
    fn delete(&self, row_id: i64) -> Result<()> {
        self.execute("DELETE FROM downloads WHERE id=?", &[json!(row_id)])?;
        Ok(())
    }
    fn clear_finished(&self) -> Result<usize> {
        self.execute(
            "DELETE FROM downloads WHERE status IN ('complete','removed','error')",
            &[],
        )
    }
    fn automation_enqueue(&self, gid: &str, action: &str, payload: Option<&JsonMap>) -> Result<()> {
        self.execute("INSERT OR IGNORE INTO automation_jobs(download_gid,action,payload,created_at) VALUES(?,?,?,?)",&[json!(gid),json!(action),json!(json!(payload.cloned().unwrap_or_default()).to_string()),json!(now())])?;
        Ok(())
    }
    fn automation_jobs(&self, gid: &str, limit: usize) -> Result<Vec<Json>> {
        Ok(jobs(if gid.is_empty() {
            self.query(
                "SELECT * FROM automation_jobs ORDER BY id DESC LIMIT ?",
                &[json!(limit)],
            )?
        } else {
            self.query(
                "SELECT * FROM automation_jobs WHERE download_gid=? ORDER BY id",
                &[json!(gid)],
            )?
        }))
    }
    fn automation_claim(&self) -> Result<Option<Json>> {
        let mut conn = self.lock()?;
        let tx = conn.transaction().map_err(db_error)?;
        let rows=query_conn(&tx,"SELECT * FROM automation_jobs WHERE status IN ('queued','running') ORDER BY id LIMIT 1",&[])?;
        let Some(row) = rows.first() else {
            return Ok(None);
        };
        let id = row["id"]
            .as_i64()
            .ok_or_else(|| AfuError::Db("Is kimligi gecersiz.".into()))?;
        tx.execute("UPDATE automation_jobs SET status='running',attempt=attempt+1,started_at=?,error=NULL WHERE id=?",params![now(),id]).map_err(db_error)?;
        let row = jobs(query_conn(
            &tx,
            "SELECT * FROM automation_jobs WHERE id=?",
            &[json!(id)],
        )?)
        .pop();
        tx.commit().map_err(db_error)?;
        Ok(row)
    }
    fn automation_jobs_by_id(&self, job_id: i64) -> Result<Option<Json>> {
        Ok(jobs(self.query("SELECT * FROM automation_jobs WHERE id=?", &[json!(job_id)])?).pop())
    }
    fn automation_update(&self, job_id: i64, fields: &JsonMap) -> Result<()> {
        self.update("automation_jobs", "id", json!(job_id), fields)
    }
    fn automation_retry(&self, job_id: i64) -> Result<()> {
        self.automation_update(
            job_id,
            &JsonMap::from_iter([
                ("status".into(), json!("queued")),
                ("progress".into(), json!(0)),
                ("error".into(), Json::Null),
                ("finished_at".into(), Json::Null),
            ]),
        )
    }
    fn automation_cancel(&self, job_id: i64) -> Result<()> {
        self.automation_update(
            job_id,
            &JsonMap::from_iter([
                ("status".into(), json!("cancelled")),
                ("finished_at".into(), json!(now())),
            ]),
        )
    }
    fn eklenti_listesi(&self) -> Result<Vec<Json>> {
        Ok(plugins(
            self.query("SELECT * FROM plugins ORDER BY ad", &[])?,
        ))
    }
    fn eklenti(&self, ad: &str) -> Result<Option<Json>> {
        Ok(plugins(self.query("SELECT * FROM plugins WHERE ad=?", &[json!(ad)])?).pop())
    }
    fn eklenti_yaz(&self, kayit: &JsonMap) -> Result<()> {
        let ad = kayit
            .get("ad")
            .ok_or_else(|| AfuError::Invalid("ad".into()))?;
        let columns = [
            "ad",
            "baslik",
            "surum",
            "kaynak",
            "giris",
            "manifest",
            "izinler",
            "domainler",
            "ayarlar",
            "etkin",
            "son_hata",
            "onceki_surum",
            "sha256",
            "kurulum_at",
            "guncelleme_at",
        ];
        let mut args = vec![json!(crate::settings::py_string(ad))];
        for key in &columns[1..] {
            let value = kayit.get(*key).filter(|v| truthy(v));
            args.push(match *key {
                "manifest" | "ayarlar" => json!(value.cloned().unwrap_or(json!({})).to_string()),
                "izinler" | "domainler" => json!(value.cloned().unwrap_or(json!([])).to_string()),
                "etkin" => json!(value.is_some()),
                "kurulum_at" | "guncelleme_at" => json!(match value {
                    None => now(),
                    Some(v) => v
                        .as_f64()
                        .or_else(|| v.as_str().and_then(|s| s.parse().ok()))
                        .ok_or_else(|| AfuError::Invalid("Gecersiz zaman.".into()))?,
                }),
                "son_hata" => json!(value
                    .map(crate::settings::py_string)
                    .unwrap_or_default()
                    .chars()
                    .take(500)
                    .collect::<String>()),
                _ => json!(value.map(crate::settings::py_string).unwrap_or_default()),
            });
        }
        let updates = columns[1..]
            .iter()
            .filter(|k| **k != "kurulum_at")
            .map(|k| format!("{k}=excluded.{k}"))
            .collect::<Vec<_>>()
            .join(",");
        self.execute(
            &format!(
                "INSERT INTO plugins({}) VALUES({}) ON CONFLICT(ad) DO UPDATE SET {updates}",
                columns.join(","),
                vec!["?"; columns.len()].join(",")
            ),
            &args,
        )?;
        Ok(())
    }
    fn eklenti_alan_yaz(&self, ad: &str, alanlar: &JsonMap) -> Result<()> {
        let mut fields = JsonMap::new();
        for (k, v) in alanlar {
            let v = match k.as_str() {
                "manifest" | "izinler" | "domainler" | "ayarlar" => json!(v.to_string()),
                "etkin" => json!(match v {
                    Json::Bool(b) => i64::from(*b),
                    _ => crate::settings::python_int(v)
                        .ok_or_else(|| AfuError::Invalid("etkin".into()))?,
                }),
                "baslik" | "surum" | "kaynak" | "giris" | "son_hata" | "onceki_surum"
                | "sha256" | "guncelleme_at" => v.clone(),
                _ => continue,
            };
            fields.insert(k.clone(), v);
        }
        self.update("plugins", "ad", json!(ad), &fields)
    }
    fn eklenti_sil(&self, ad: &str) -> Result<()> {
        self.execute("DELETE FROM plugins WHERE ad=?", &[json!(ad)])?;
        Ok(())
    }
    fn log(&self, level: &str, message: &str, gid: &str) {
        let _ = self.execute(
            "INSERT INTO events(at,level,message,gid) VALUES(?,?,?,?)",
            &[
                json!(now()),
                json!(level),
                json!(message),
                if gid.is_empty() {
                    Json::Null
                } else {
                    json!(gid)
                },
            ],
        );
    }
    fn recent_events(&self, limit: usize, gid: &str) -> Result<Vec<Json>> {
        if gid.is_empty() {
            self.query(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?",
                &[json!(limit)],
            )
        } else {
            self.query(
                "SELECT * FROM events WHERE gid=? ORDER BY id DESC LIMIT ?",
                &[json!(gid), json!(limit)],
            )
        }
    }
}
