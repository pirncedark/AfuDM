//! Python semantigi yardimcilari (truthy, str(), int(), float(), ==).
//! Python kaynagindaki `or`, `str(x)`, `int(x)` davranisini birebir tasir.

use afudm_types::{AfuError, Json, Result};

/// Python `bool(x)`.
pub fn truthy(v: &Json) -> bool {
    match v {
        Json::Null => false,
        Json::Bool(b) => *b,
        Json::Number(n) => n.as_f64().map(|f| f != 0.0).unwrap_or(true),
        Json::String(s) => !s.is_empty(),
        Json::Array(a) => !a.is_empty(),
        Json::Object(o) => !o.is_empty(),
    }
}

/// Python `str(x)` (sayi, bool ve None icin Python gosterimi).
pub fn py_str(v: &Json) -> String {
    match v {
        Json::Null => "None".into(),
        Json::Bool(true) => "True".into(),
        Json::Bool(false) => "False".into(),
        Json::Number(n) => match n.as_i64() {
            Some(i) => i.to_string(),
            None => n.as_f64().map(py_float).unwrap_or_else(|| n.to_string()),
        },
        Json::String(s) => s.clone(),
        other => other.to_string(),
    }
}

/// Python `repr(float)` benzeri: tam sayi degerler `.0` ile biter.
pub fn py_float(f: f64) -> String {
    if f.is_nan() {
        "nan".into()
    } else if f.is_infinite() {
        if f > 0.0 {
            "inf".into()
        } else {
            "-inf".into()
        }
    } else {
        format!("{f:?}")
    }
}

/// Python `float(x)`; yapilamazsa None (Python'da TypeError/ValueError).
pub fn py_float_of(v: &Json) -> Option<f64> {
    match v {
        Json::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
        Json::Number(n) => n.as_f64(),
        Json::String(s) => s.trim().parse::<f64>().ok(),
        _ => None,
    }
}

/// Python `int(x)`; yapilamazsa `AfuError::Invalid` (Python'da ValueError/TypeError).
pub fn py_int(v: &Json) -> Result<i64> {
    match v {
        Json::Bool(b) => Ok(i64::from(*b)),
        Json::Number(n) => match n.as_i64() {
            Some(i) => Ok(i),
            None => n
                .as_f64()
                .filter(|f| f.is_finite())
                .map(|f| f.trunc() as i64)
                .ok_or_else(|| AfuError::Invalid("int() gecersiz sayi".into())),
        },
        Json::String(s) => s
            .trim()
            .parse::<i64>()
            .map_err(|_| AfuError::Invalid(format!("invalid literal for int(): '{s}'"))),
        _ => Err(AfuError::Invalid("int() desteklenmeyen tur".into())),
    }
}

/// Python `a == b` (sayilar kendi aralarinda sayisal karsilastirilir).
pub fn py_esit(a: &Json, b: &Json) -> bool {
    match (a, b) {
        (Json::Number(_), Json::Number(_)) => py_float_of(a) == py_float_of(b),
        _ => a == b,
    }
}

/// `str(x or "").strip()` kalibi: falsy ise bos, aksi halde str(x).strip().
pub fn py_metin_veya_bos(v: Option<&Json>) -> String {
    match v {
        Some(x) if truthy(x) => py_str(x).trim().to_string(),
        _ => String::new(),
    }
}

/// Python `s[:n]` (kod noktasi sayisi uzerinden kesme).
pub fn kes(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn truthy_python_gibi() {
        assert!(!truthy(&json!(null)));
        assert!(!truthy(&json!("")));
        assert!(!truthy(&json!(0)));
        assert!(truthy(&json!([1])));
        assert!(!truthy(&json!({})));
    }

    #[test]
    fn str_ve_int_python_gibi() {
        assert_eq!(py_str(&json!(true)), "True");
        assert_eq!(py_str(&json!(null)), "None");
        assert_eq!(py_str(&json!(1.0)), "1.0");
        assert_eq!(py_int(&json!("  42 ")).unwrap(), 42);
        assert_eq!(py_int(&json!(3.9)).unwrap(), 3);
        assert!(py_int(&json!("abc")).is_err());
        assert!(py_int(&json!(null)).is_err());
    }

    #[test]
    fn esitlik_sayisal() {
        assert!(py_esit(&json!(1), &json!(1.0)));
        assert!(!py_esit(&json!("1"), &json!(1)));
    }
}
