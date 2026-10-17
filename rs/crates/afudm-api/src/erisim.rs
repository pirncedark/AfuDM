//! Role/key/client storage from core/erisim.py. LocalAPI still uses its file token.
use afudm_types::{AfuError, Json, JsonMap, Result, Store};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
    time::{SystemTime, UNIX_EPOCH},
};
use subtle::ConstantTimeEq;
fn now() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|v| v.as_secs_f64())
        .unwrap_or(0.0)
}
fn digest(value: &str) -> String {
    format!("{:x}", Sha256::digest(value.as_bytes()))
}
fn invalid(message: &str) -> AfuError {
    AfuError::Invalid(message.into())
}
fn role(value: &str) -> Result<String> {
    let value = value.trim().to_lowercase();
    if ["yonetici", "salt_okur"].contains(&value.as_str()) {
        Ok(value)
    } else {
        Err(invalid("rol 'yonetici' veya 'salt_okur' olmali"))
    }
}
fn key_out(mut row: Json) -> Json {
    if let Some(row) = row.as_object_mut() {
        row.remove("gizli_hash");
        row.insert(
            "iptal".into(),
            json!(row.get("iptal").is_some_and(crate::request::truthy)),
        );
        if row.get("not_metni").is_none_or(|v| v.is_null()) {
            row.insert("not_metni".into(), json!(""));
        }
    }
    row
}
fn client_out(mut row: Json) -> Json {
    if let Some(row) = row.as_object_mut() {
        row.remove("oturum");
        row.insert(
            "iptal".into(),
            json!(row.get("iptal").is_some_and(crate::request::truthy)),
        );
        row.entry("anahtar_adi").or_insert(Json::Null);
    }
    row
}
/// Python role permissions: administrator can read/write/settings/admin; reader can read.
pub fn izinli(rol: &str, izin: &str) -> bool {
    match rol {
        "yonetici" => ["oku", "yaz", "ayar", "yonet"].contains(&izin),
        "salt_okur" => izin == "oku",
        _ => false,
    }
}
/// Safe event-log representation; full client addresses stay in the admin client list.
pub fn ip_maskele(ip: &str) -> String {
    if ip.contains(':') {
        return format!("{}:x", ip.split(':').take(3).collect::<Vec<_>>().join(":"));
    }
    let parts = ip.split('.').collect::<Vec<_>>();
    if parts.len() == 4 {
        format!("{}.x", parts[..3].join("."))
    } else {
        "?".into()
    }
}
/// Store SQL is parameterized. Multi-statement mutations are serialized per depot.
pub struct ErisimDeposu {
    store: Arc<dyn Store>,
    lock: Mutex<()>,
}
impl ErisimDeposu {
    pub fn new(store: Arc<dyn Store>) -> Self {
        Self {
            store,
            lock: Mutex::new(()),
        }
    }
    /// Invoke the corresponding Python depot method; input keys use Python argument names.
    /// This is a service interface, not an additional HTTP endpoint.
    pub fn call(&self, action: &str, data: &JsonMap) -> Result<Json> {
        let _guard = self
            .lock
            .lock()
            .map_err(|_| AfuError::Other("Erisim kilidi acilamadi".into()))?;
        let s = |key: &str| crate::text(data, key);
        let n = |key: &str| data.get(key).and_then(Json::as_i64).unwrap_or(0);
        let key_id = n("key_id");
        match action {
            "anahtar_olustur" => {
                let ad = s("ad").trim().chars().take(64).collect::<String>();
                if ad.is_empty() {
                    return Err(invalid("anahtar adi gerekli"));
                }
                let rol = role(s("rol"))?;
                let gizli = format!("afudm_{}", crate::security::secret(32));
                let stamp = now();
                let rows=self.store.query("INSERT INTO api_keys(ad,rol,gizli_hash,onek,olusturuldu,not_metni) VALUES(?,?,?,?,?,?) RETURNING id",&[json!(ad),json!(rol),json!(digest(&gizli)),json!(&gizli[6..12]),json!(stamp),json!(s("not_metni").chars().take(200).collect::<String>())])?;
                let id = rows
                    .first()
                    .and_then(|v| v.get("id"))
                    .cloned()
                    .ok_or_else(|| AfuError::Db("Anahtar kaydedilemedi".into()))?;
                self.store.log(
                    "info",
                    &format!("erisim anahtari olusturuldu: {ad} ({rol})"),
                    "",
                );
                Ok(json!({"id":id,"ad":ad,"rol":rol,"gizli":gizli,"olusturuldu":stamp}))
            }
            "anahtar" => Ok(self.key(key_id)?.map(key_out).unwrap_or(Json::Null)),
            "anahtarlar" => Ok(json!(self
                .store
                .query(
                    "SELECT * FROM api_keys ORDER BY iptal ASC, olusturuldu DESC",
                    &[]
                )?
                .into_iter()
                .map(key_out)
                .collect::<Vec<_>>())),
            "dogrula" => {
                let supplied = s("sunulan");
                if supplied.is_empty() {
                    return Ok(Json::Null);
                }
                let hash = digest(supplied);
                for row in self
                    .store
                    .query("SELECT * FROM api_keys WHERE iptal = 0", &[])?
                {
                    if bool::from(
                        row["gizli_hash"]
                            .as_str()
                            .unwrap_or("")
                            .as_bytes()
                            .ct_eq(hash.as_bytes()),
                    ) {
                        return Ok(key_out(row));
                    }
                }
                Ok(Json::Null)
            }
            "anahtar_rotasyon" => {
                let row = self
                    .key(key_id)?
                    .ok_or_else(|| invalid("anahtar bulunamadi"))?;
                if crate::request::truthy(&row["iptal"]) {
                    return Err(invalid("iptal edilmis anahtar yenilenemez"));
                }
                let gizli = format!("afudm_{}", crate::security::secret(32));
                let stamp = now();
                self.store.execute(
                    "UPDATE api_keys SET gizli_hash=?, onek=?, son_rotasyon=? WHERE id=?",
                    &[
                        json!(digest(&gizli)),
                        json!(&gizli[6..12]),
                        json!(stamp),
                        json!(key_id),
                    ],
                )?;
                self.store.execute(
                    "UPDATE api_clients SET iptal=1 WHERE key_id=?",
                    &[json!(key_id)],
                )?;
                self.store.log(
                    "info",
                    &format!(
                        "erisim anahtari yenilendi: {}",
                        row["ad"].as_str().unwrap_or("")
                    ),
                    "",
                );
                Ok(
                    json!({"id":key_id,"ad":row["ad"],"rol":row["rol"],"gizli":gizli,"son_rotasyon":stamp}),
                )
            }
            "anahtar_iptal" => {
                let row = self
                    .key(key_id)?
                    .ok_or_else(|| invalid("anahtar bulunamadi"))?;
                self.store
                    .execute("UPDATE api_keys SET iptal=1 WHERE id=?", &[json!(key_id)])?;
                self.store.execute(
                    "UPDATE api_clients SET iptal=1 WHERE key_id=?",
                    &[json!(key_id)],
                )?;
                self.store.log(
                    "info",
                    &format!(
                        "erisim anahtari iptal edildi: {}",
                        row["ad"].as_str().unwrap_or("")
                    ),
                    "",
                );
                Ok(json!({"id":key_id,"iptal":true}))
            }
            "anahtar_sil" => {
                self.store.execute(
                    "DELETE FROM api_keys WHERE id=? AND iptal=1",
                    &[json!(key_id)],
                )?;
                self.store
                    .execute("DELETE FROM api_clients WHERE key_id=?", &[json!(key_id)])?;
                Ok(json!({"id":key_id,"silindi":true}))
            }
            "anahtar_rol_ayarla" => {
                let rol = role(s("rol"))?;
                if self.key(key_id)?.is_none() {
                    return Err(invalid("anahtar bulunamadi"));
                }
                self.store.execute(
                    "UPDATE api_keys SET rol=? WHERE id=?",
                    &[json!(rol), json!(key_id)],
                )?;
                self.store.execute(
                    "UPDATE api_clients SET rol=? WHERE key_id=?",
                    &[json!(rol), json!(key_id)],
                )?;
                Ok(json!({"id":key_id,"rol":rol}))
            }
            "kullanim_isle" => {
                self.store.execute(
                    "UPDATE api_keys SET son_kullanim=? WHERE id=?",
                    &[json!(now()), json!(key_id)],
                )?;
                Ok(Json::Null)
            }
            "yonetici_var_mi" => Ok(json!(!self
                .store
                .query(
                    "SELECT 1 FROM api_keys WHERE iptal=0 AND rol=?",
                    &[json!("yonetici")]
                )?
                .is_empty())),
            "oturum_ac" => {
                let token = crate::security::secret(18);
                let stamp = now();
                self.store.execute("INSERT INTO api_clients(key_id,oturum,ip,istemci,rol,ilk_gorulme,son_gorulme,istek_sayisi) VALUES(?,?,?,?,?,?,?,0)",&[json!(key_id),json!(token),json!(s("ip").chars().take(64).collect::<String>()),json!(s("istemci").chars().take(120).collect::<String>()),json!(s("rol")),json!(stamp),json!(stamp)])?;
                Ok(json!(token))
            }
            "oturum_dokun" => {
                let rows = self.store.query(
                    "SELECT * FROM api_clients WHERE oturum=?",
                    &[json!(s("oturum"))],
                )?;
                let Some(row) = rows
                    .first()
                    .filter(|v| !crate::request::truthy(&v["iptal"]))
                else {
                    return Ok(Json::Null);
                };
                self.store.execute("UPDATE api_clients SET son_gorulme=?, istek_sayisi=istek_sayisi+1, ip=COALESCE(NULLIF(?,''),ip) WHERE oturum=?",&[json!(now()),json!(s("ip").chars().take(64).collect::<String>()),json!(s("oturum"))])?;
                Ok(client_out(row.clone()))
            }
            "istemciler" => {
                let mut sql="SELECT c.*, k.ad AS anahtar_adi FROM api_clients c LEFT JOIN api_keys k ON k.id=c.key_id".to_string();
                let mut args = Vec::new();
                if n("dakika") > 0 {
                    sql.push_str(" WHERE c.son_gorulme >= ?");
                    args.push(json!(now() - n("dakika") as f64 * 60.0));
                }
                sql.push_str(" ORDER BY c.son_gorulme DESC LIMIT 200");
                Ok(json!(self
                    .store
                    .query(&sql, &args)?
                    .into_iter()
                    .map(client_out)
                    .collect::<Vec<_>>()))
            }
            "oturum_iptal" => {
                self.store.execute(
                    "UPDATE api_clients SET iptal=1 WHERE id=?",
                    &[json!(n("client_id"))],
                )?;
                Ok(json!({"id":n("client_id"),"iptal":true}))
            }
            "oturumlari_temizle" => Ok(json!(self.store.execute(
                "DELETE FROM api_clients WHERE iptal=1 AND son_gorulme < ?",
                &[json!(
                    now() - data.get("gun").and_then(Json::as_i64).unwrap_or(7) as f64 * 86400.0
                )]
            )?)),
            "profil_kaydet" => {
                let ad = s("ad").trim().chars().take(48).collect::<String>();
                if ad.is_empty() {
                    return Err(invalid("profil adi gerekli"));
                }
                let adres = if s("adres").is_empty() {
                    "yerel"
                } else {
                    s("adres")
                }
                .trim()
                .to_lowercase();
                if !["yerel", "lan"].contains(&adres.as_str()) {
                    return Err(invalid("adres 'yerel' veya 'lan' olmali"));
                }
                let port = n("port");
                if !(1024..=65535).contains(&port) {
                    return Err(invalid("port 1024-65535 araliginda olmali"));
                }
                let limit = match n("istek_limiti") {
                    0 => 120,
                    v => v.clamp(1, 100000),
                };
                let originler = s("originler").trim().chars().take(500).collect::<String>();
                let mut id = n("profil_id");
                if id != 0 {
                    self.store.execute("UPDATE server_profiles SET ad=?,adres=?,port=?,originler=?,istek_limiti=? WHERE id=?",&[json!(ad),json!(adres),json!(port),json!(originler),json!(limit),json!(id)])?;
                } else {
                    let rows=self.store.query("INSERT INTO server_profiles(ad,adres,port,originler,istek_limiti,olusturuldu) VALUES(?,?,?,?,?,?) RETURNING id",&[json!(ad),json!(adres),json!(port),json!(originler),json!(limit),json!(now())])?;
                    id = rows
                        .first()
                        .and_then(|r| r["id"].as_i64())
                        .ok_or_else(|| AfuError::Db("Profil kaydedilemedi".into()))?;
                }
                Ok(
                    json!({"id":id,"ad":ad,"adres":adres,"port":port,"originler":originler,"istek_limiti":limit}),
                )
            }
            "profil_sil" => {
                let id = n("profil_id");
                self.store
                    .execute("DELETE FROM server_profiles WHERE id=?", &[json!(id)])?;
                if self.store.get("sunucu_profil_id")? == Some(json!(id)) {
                    self.store.set("sunucu_profil_id", json!(0))?;
                }
                Ok(json!({"id":id,"silindi":true}))
            }
            "profiller" | "profil" => {
                let active = self.store.get("sunucu_profil_id")?.unwrap_or(json!(0));
                let mut rows = self.store.query(
                    "SELECT * FROM server_profiles ORDER BY olusturuldu ASC",
                    &[],
                )?;
                for row in &mut rows {
                    row["etkin"] = json!(row["id"] == active);
                }
                if action == "profil" {
                    Ok(rows
                        .into_iter()
                        .find(|v| v["id"] == json!(n("profil_id")))
                        .unwrap_or(Json::Null))
                } else {
                    Ok(json!(rows))
                }
            }
            _ => Err(invalid("bilinmeyen erisim islemi")),
        }
    }
    fn key(&self, id: i64) -> Result<Option<Json>> {
        Ok(self
            .store
            .query("SELECT * FROM api_keys WHERE id=?", &[json!(id)])?
            .into_iter()
            .next())
    }
}
#[derive(Default)]
struct RateState {
    hits: HashMap<String, Vec<f64>>,
    errors: HashMap<String, u32>,
    locks: HashMap<String, f64>,
}
/// In-memory sliding window and failed-auth lock from HizSinirlayici.
pub struct HizSinirlayici {
    limit: usize,
    hatali_limit: u32,
    kilit_saniye: f64,
    state: Mutex<RateState>,
}
impl HizSinirlayici {
    pub fn new(limit: usize, hatali_limit: u32, kilit_saniye: u32) -> Self {
        Self {
            limit: limit.max(1),
            hatali_limit: hatali_limit.max(1),
            kilit_saniye: kilit_saniye.max(5) as f64,
            state: Mutex::new(RateState::default()),
        }
    }
    /// Canli ayar (Python HizSinirlayici.ayarla): yeni degerler hemen gecerli, yeniden baslatma yok.
    pub fn ayarla(&mut self, limit: Option<usize>, hatali_limit: Option<u32>, kilit_saniye: Option<u32>) {
        if let Some(v) = limit {
            self.limit = v.max(1);
        }
        if let Some(v) = hatali_limit {
            self.hatali_limit = v.max(1);
        }
        if let Some(v) = kilit_saniye {
            self.kilit_saniye = v.max(5) as f64;
        }
    }
    /// Check/record an attempt, or record auth success/failure, or clear locks.
    pub fn call(&self, action: &str, ip: &str) -> Result<Json> {
        let mut state = self
            .state
            .lock()
            .map_err(|_| AfuError::Other("Erisim kilidi acilamadi".into()))?;
        let stamp = now();
        match action {
            "kilitli_mi" => Ok(json!(
                (state.locks.get(ip).copied().unwrap_or(0.0) - stamp).max(0.0)
            )),
            "izin_ver" => {
                let remaining = (state.locks.get(ip).copied().unwrap_or(0.0) - stamp).max(0.0);
                if remaining > 0.0 {
                    return Ok(json!([false, remaining]));
                }
                let hits = state.hits.entry(ip.into()).or_default();
                hits.retain(|v| stamp - v < 60.0);
                let allowed = hits.len() < self.limit;
                hits.push(stamp);
                let remaining = if allowed {
                    0.0
                } else {
                    (60.0 - (stamp - hits[0])).max(0.0)
                };
                if hits.len() > self.limit * 2 {
                    hits.drain(..hits.len() - self.limit * 2);
                }
                Ok(json!([allowed, remaining]))
            }
            "hatali" => {
                let count = state.errors.entry(ip.into()).or_default();
                *count += 1;
                if *count >= self.hatali_limit {
                    *count = 0;
                    state.locks.insert(ip.into(), stamp + self.kilit_saniye);
                }
                Ok(Json::Null)
            }
            "basarili" => {
                state.errors.remove(ip);
                Ok(Json::Null)
            }
            "kilitleri_temizle" => {
                let count = state.locks.len();
                state.locks.clear();
                state.errors.clear();
                Ok(json!(count))
            }
            "durum" => Ok(
                json!({"limit":self.limit,"pencere_sn":60,"hatali_limit":self.hatali_limit,"kilit_saniye":self.kilit_saniye as u64,"izlenen_ip":state.hits.len(),"kilitli_ip":state.locks.values().filter(|v|**v>stamp).count(),"kalici":false}),
            ),
            _ => Err(invalid("bilinmeyen hiz siniri islemi")),
        }
    }
}
