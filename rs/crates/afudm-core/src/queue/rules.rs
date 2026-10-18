use super::{number, text, truthy};
use afudm_types::{Json, JsonMap};
use serde_json::json;

const KEYS: [&str; 6] = [
    "dest_dir",
    "proxy",
    "max_speed_kb",
    "split",
    "start_after",
    "automation_script",
];

fn one(condition: &Json, ctx: &Json) -> bool {
    let value = ctx
        .get(text(&condition["field"]))
        .cloned()
        .unwrap_or(json!(""));
    let wanted = &condition["value"];
    let a = text(&value).to_lowercase();
    let b = text(wanted).to_lowercase();
    match text(&condition["op"]) {
        "eq" => value == *wanted,
        "neq" => value != *wanted,
        "contains" => a.contains(&b),
        "ends_with" => a.ends_with(&b),
        "regex" => regex::RegexBuilder::new(text(wanted))
            .case_insensitive(true)
            .build()
            .is_ok_and(|r| r.is_match(text(&value))),
        "in" => wanted.as_array().is_some_and(|v| v.contains(&value)),
        "gt" => float(&value).zip(float(wanted)).is_some_and(|(a, b)| a > b),
        "lt" => float(&value).zip(float(wanted)).is_some_and(|(a, b)| a < b),
        _ => false,
    }
}

fn float(v: &Json) -> Option<f64> {
    v.as_f64()
        .or_else(|| v.as_str().and_then(|s| s.parse().ok()))
}

pub(super) fn evaluate(
    rules: &[Json],
    defaults: JsonMap,
    req: &JsonMap,
    kind: &str,
) -> (JsonMap, JsonMap) {
    let source = req.get("source").and_then(Json::as_str).unwrap_or("");
    let parsed = url::Url::parse(source).ok();
    let filename = req
        .get("filename")
        .or_else(|| req.get("title"))
        .and_then(Json::as_str)
        .filter(|s| !s.is_empty())
        .map(str::to_owned)
        .unwrap_or_else(|| {
            parsed
                .as_ref()
                .map(|u| u.path().rsplit('/').next().unwrap_or("").to_owned())
                .unwrap_or_default()
        });
    let ctx = json!({"domain":parsed.as_ref().and_then(|u|u.host_str()).unwrap_or("").to_lowercase(),"extension":filename.rsplit_once('.').map(|(_,e)|e.to_lowercase()).unwrap_or_default(),"filename":filename,"size_mb":0.0,"protocol":kind.to_lowercase(),"category":if ["torrent","video"].contains(&kind){kind}else{""}});
    let mut options: JsonMap = defaults
        .into_iter()
        .filter(|(k, v)| KEYS.contains(&k.as_str()) && !v.is_null() && *v != json!(""))
        .collect();
    let mut trace: JsonMap = options
        .keys()
        .map(|k| {
            (
                k.clone(),
                json!({"source":"default","source_id":null,"source_name":"Genel Ayarlar"}),
            )
        })
        .collect();
    let mut matches: Vec<_> = rules
        .iter()
        .filter(|r| {
            if r.get("active").is_some_and(|v| !truthy(v)) {
                return false;
            }
            let values: Vec<_> = r["conditions"]
                .as_array()
                .into_iter()
                .flatten()
                .filter(|c| c.is_object())
                .map(|c| one(c, &ctx))
                .collect();
            if r.get("match_type").and_then(Json::as_str).unwrap_or("all") == "all" {
                values.iter().all(|b| *b)
            } else {
                values.iter().any(|b| *b)
            }
        })
        .collect();
    matches.sort_by_key(|r| std::cmp::Reverse(r.get("priority").map(number).unwrap_or(999999)));
    for rule in matches {
        if let Some(actions) = rule["actions"].as_object() {
            for (k, v) in actions {
                if KEYS.contains(&k.as_str()) && !v.is_null() && *v != json!("") {
                    options.insert(k.clone(), v.clone());
                    trace.insert(k.clone(),json!({"source":"rule","source_id":rule["id"],"source_name":rule.get("name").cloned().unwrap_or(json!("Kural"))}));
                }
            }
        }
    }
    for k in ["dest_dir", "proxy"] {
        if let Some(v) = req.get(k).filter(|v| !v.is_null() && **v != json!("")) {
            options.insert(k.into(), v.clone());
            trace.insert(
                k.into(),
                json!({"source":"user","source_id":null,"source_name":"Bu indirme"}),
            );
        }
    }
    (options, trace)
}
