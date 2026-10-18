//! core/rules.py karsiligi — bildirimsel indirme kurallari. Durumsuz.
//!
//! Not: `afudm-core` icindeki `queue::rules` ozel bir kuyruk kopyasidir (farkli davranis:
//! ornegin `size_mb` sabit 0). Bu modul Python `rules.py` ile birebir eslesir.

use super::py::{py_esit, py_float_of, py_int, py_str, truthy};
use super::url_parca::{hostname, urlsplit};
use afudm_types::{AfuError, Json, JsonMap, Result};
use serde_json::json;

pub const ACTION_KEYS: [&str; 6] = [
    "dest_dir",
    "proxy",
    "max_speed_kb",
    "split",
    "start_after",
    "automation_script",
];

/// Python `context`: kural kosullarinin degerlendigi alanlar.
pub fn context(url: &str, filename: &str, size_bytes: f64, protocol: &str, category: &str) -> Json {
    let p = urlsplit(url);
    let name = if filename.is_empty() {
        p.path.rsplit('/').next().unwrap_or("").to_string()
    } else {
        filename.to_string()
    };
    let extension = name
        .rsplit_once('.')
        .map(|(_, e)| e.to_lowercase())
        .unwrap_or_default();
    json!({
        "domain": hostname(&p.netloc),
        "extension": extension,
        "filename": name,
        "size_mb": size_bytes / 1048576.0,
        "protocol": protocol.to_lowercase(),
        "category": category.to_lowercase(),
    })
}

fn tek_kosul(c: &Json, ctx: &Json) -> bool {
    let alan = c.get("field").and_then(Json::as_str).unwrap_or("");
    let value = ctx.get(alan).cloned().unwrap_or(json!(""));
    let wanted = c.get("value").cloned().unwrap_or(Json::Null);
    match c.get("op").and_then(Json::as_str).unwrap_or("") {
        "eq" => py_esit(&value, &wanted),
        "neq" => !py_esit(&value, &wanted),
        "contains" => py_str(&value)
            .to_lowercase()
            .contains(&py_str(&wanted).to_lowercase()),
        "ends_with" => py_str(&value)
            .to_lowercase()
            .ends_with(&py_str(&wanted).to_lowercase()),
        "regex" => regex::RegexBuilder::new(&py_str(&wanted))
            .case_insensitive(true)
            .build()
            .map(|r| r.is_match(&py_str(&value)))
            .unwrap_or(false),
        "in" => wanted
            .as_array()
            .is_some_and(|liste| liste.iter().any(|x| py_esit(&value, x))),
        "gt" => matches!((py_float_of(&value), py_float_of(&wanted)), (Some(a), Some(b)) if a > b),
        "lt" => matches!((py_float_of(&value), py_float_of(&wanted)), (Some(a), Some(b)) if a < b),
        _ => false,
    }
}

/// Python `matches`: kural aktif mi ve kosullari (all/any) saglaniyor mu.
pub fn matches(rule: &Json, ctx: &Json) -> bool {
    if rule.get("active").is_some_and(|v| !truthy(v)) {
        return false;
    }
    let kosullar = rule.get("conditions").and_then(Json::as_array);
    let degerler = kosullar
        .into_iter()
        .flatten()
        .filter(|c| c.is_object())
        .map(|c| tek_kosul(c, ctx));
    let hepsi = match rule.get("match_type") {
        None => true,
        Some(v) => v.as_str() == Some("all"),
    };
    if hepsi {
        degerler.into_iter().all(|b| b)
    } else {
        degerler.into_iter().any(|b| b)
    }
}

fn bos_mu(v: &Json) -> bool {
    v.is_null() || v.as_str() == Some("")
}

/// Python `evaluate`: varsayilanlar < kurallar (oncelik sirasina gore) < kullanici.
/// Hatali `priority` degeri Python'daki gibi `int()` hatasi verir.
pub fn evaluate(
    rules: &[Json],
    defaults: &JsonMap,
    ctx: &Json,
    overrides: Option<&JsonMap>,
) -> Result<Json> {
    let mut options = JsonMap::new();
    let mut trace = JsonMap::new();
    for k in ACTION_KEYS {
        if let Some(v) = defaults.get(k).filter(|v| !bos_mu(v)) {
            options.insert(k.into(), v.clone());
            trace.insert(
                k.into(),
                json!({"source": "default", "source_id": null, "source_name": "Genel Ayarlar"}),
            );
        }
    }

    let bulunan: Vec<&Json> = rules.iter().filter(|r| matches(r, ctx)).collect();
    let mut oncelikli: Vec<(i64, &Json)> = Vec::with_capacity(bulunan.len());
    for &r in &bulunan {
        let oncelik = match r.get("priority") {
            None => 999_999,
            Some(v) => py_int(v)?,
        };
        oncelikli.push((oncelik, r));
    }
    // Python: sorted(..., reverse=True) — kararli siralama, esitlikte sira korunur.
    oncelikli.sort_by_key(|(k, _)| std::cmp::Reverse(*k));

    for (_, rule) in oncelikli {
        let Some(actions) = rule.get("actions").and_then(Json::as_object) else {
            continue;
        };
        for (k, v) in actions {
            if ACTION_KEYS.contains(&k.as_str()) && !bos_mu(v) {
                options.insert(k.clone(), v.clone());
                trace.insert(
                    k.clone(),
                    json!({
                        "source": "rule",
                        "source_id": rule.get("id").cloned().unwrap_or(Json::Null),
                        "source_name": rule.get("name").cloned().unwrap_or(json!("Kural")),
                    }),
                );
            }
        }
    }

    for (k, v) in overrides.into_iter().flatten() {
        if ACTION_KEYS.contains(&k.as_str()) && !bos_mu(v) {
            options.insert(k.clone(), v.clone());
            trace.insert(
                k.clone(),
                json!({"source": "user", "source_id": null, "source_name": "Bu indirme"}),
            );
        }
    }

    Ok(json!({
        "matched_rules": bulunan.iter().map(|r| r.get("id").cloned().unwrap_or(Json::Null)).collect::<Vec<_>>(),
        "effective_options": options,
        "trace": trace,
    }))
}

/// HTTP `POST /rules` govdesini dogrular ve normalize eder (Python: server.py `/rules`).
/// `id` bos ise `id_uret(sira)` kullanilir; sira 1'den baslar.
pub fn kurallari_normalize(gelen: &[Json], id_uret: impl Fn(usize) -> String) -> Result<Vec<Json>> {
    let mut cikti = Vec::with_capacity(gelen.len());
    for (i, rule) in gelen.iter().enumerate() {
        let sira = i + 1;
        let Some(nesne) = rule.as_object() else {
            return Err(AfuError::Invalid("her kuralin adi olmali".into()));
        };
        // Python: str(rule.get("name") or "").strip() bos olamaz.
        let ad = match nesne.get("name") {
            Some(v) if truthy(v) => py_str(v),
            _ => String::new(),
        };
        if ad.trim().is_empty() {
            return Err(AfuError::Invalid("her kuralin adi olmali".into()));
        }
        let id = match nesne.get("id") {
            Some(v) if truthy(v) => py_str(v),
            _ => id_uret(sira),
        };
        let aktif = nesne.get("active").is_none_or(truthy);
        let match_type = match nesne.get("match_type").and_then(Json::as_str) {
            Some("any") => "any",
            _ => "all",
        };
        let conditions = match nesne.get("conditions") {
            Some(Json::Array(a)) => Json::Array(a.clone()),
            _ => json!([]),
        };
        let actions = match nesne.get("actions") {
            Some(Json::Object(o)) => Json::Object(o.clone()),
            _ => json!({}),
        };
        cikti.push(json!({
            "id": id,
            "name": ad.trim().chars().take(100).collect::<String>(),
            "active": aktif,
            "match_type": match_type,
            "conditions": conditions,
            "actions": actions,
        }));
    }
    Ok(cikti)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn kural(id: &str, oncelik: Option<Json>, aksiyon: Json) -> Json {
        let mut k = json!({
            "id": id, "name": format!("kural-{id}"), "active": true, "match_type": "all",
            "conditions": [{"field": "domain", "op": "ends_with", "value": "ornek.com"}],
            "actions": aksiyon,
        });
        if let Some(p) = oncelik {
            k["priority"] = p;
        }
        k
    }

    #[test]
    fn baglam_alanlari() {
        let c = context(
            "https://Dosya.Ornek.com/a/Film.MP4?x=1",
            "",
            2_097_152.0,
            "HTTP",
            "Video",
        );
        assert_eq!(c["domain"], "dosya.ornek.com");
        assert_eq!(c["extension"], "mp4");
        assert_eq!(c["filename"], "Film.MP4");
        assert_eq!(c["size_mb"], 2.0);
        assert_eq!(c["category"], "video");
    }

    #[test]
    fn kosullar_all_ve_any() {
        let c = context("https://dosya.ornek.com/a.zip", "", 0.0, "http", "");
        let all = kural("1", None, json!({}));
        assert!(matches(&all, &c));
        let mut any = all.clone();
        any["match_type"] = json!("any");
        any["conditions"] = json!([
            {"field": "extension", "op": "eq", "value": "exe"},
            {"field": "extension", "op": "in", "value": ["zip"]}
        ]);
        assert!(matches(&any, &c));
        let mut pasif = all.clone();
        pasif["active"] = json!(false);
        assert!(!matches(&pasif, &c));
    }

    #[test]
    fn regex_ve_boyut() {
        let c = context("https://x.com/a.bin", "", 3.0 * 1048576.0, "http", "");
        let r = json!({"id": "r", "conditions": [
            {"field": "filename", "op": "regex", "value": "^A\\.BIN$"},
            {"field": "size_mb", "op": "gt", "value": "2"}
        ], "match_type": "all"});
        assert!(matches(&r, &c));
        let bozuk =
            json!({"id": "b", "conditions": [{"field": "filename", "op": "regex", "value": "("}]});
        assert!(!matches(&bozuk, &c));
    }

    #[test]
    fn evaluate_oncelik_ve_kullanici() {
        let c = context("https://dosya.ornek.com/a.zip", "", 0.0, "http", "");
        let defaults = json!({"dest_dir": "C:/Indir", "split": 16, "proxy": ""})
            .as_object()
            .unwrap()
            .clone();
        let kurallar = vec![
            kural(
                "dusuk",
                Some(json!(1)),
                json!({"dest_dir": "D:/Dusuk", "split": 4}),
            ),
            kural("yuksek", Some(json!(10)), json!({"dest_dir": "D:/Yuksek"})),
        ];
        let over = json!({"proxy": "http://p:1"}).as_object().unwrap().clone();
        let out = evaluate(&kurallar, &defaults, &c, Some(&over)).unwrap();
        // Python: sorted(reverse=True) sonrasi her kural sirayla atar; sonra uygulanan (dusuk oncelik) ustune yazar.
        assert_eq!(out["effective_options"]["dest_dir"], "D:/Dusuk");
        assert_eq!(out["effective_options"]["split"], 4);
        assert_eq!(out["effective_options"]["proxy"], "http://p:1");
        assert_eq!(out["trace"]["dest_dir"]["source_id"], "dusuk");
        assert_eq!(out["trace"]["proxy"]["source"], "user");
        assert_eq!(out["matched_rules"], json!(["dusuk", "yuksek"]));
    }

    #[test]
    fn gecersiz_oncelik_hata_verir() {
        let c = context("https://dosya.ornek.com/a.zip", "", 0.0, "http", "");
        let kurallar = vec![kural("x", Some(json!("abc")), json!({}))];
        assert!(evaluate(&kurallar, &JsonMap::new(), &c, None).is_err());
    }

    #[test]
    fn normalize_alanlari_ve_hata() {
        let gelen = vec![json!({"name": "  Video  ", "conditions": "x", "match_type": "xor"})];
        let n = kurallari_normalize(&gelen, |i| format!("api-rule-{i}")).unwrap();
        assert_eq!(n[0]["id"], "api-rule-1");
        assert_eq!(n[0]["name"], "Video");
        assert_eq!(n[0]["match_type"], "all");
        assert_eq!(n[0]["conditions"], json!([]));
        assert!(kurallari_normalize(&[json!({"name": "  "})], |_| String::new()).is_err());
    }
}
