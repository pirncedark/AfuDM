//! Python `urllib.parse.urlsplit` / `urlunsplit` karsiligi (yalniz kullanilan kisim).
//! `url` crate'i kullanilmaz: o crate adresi normalize eder, Python ciktisi ise degismez.

#[derive(Debug, Default, Clone, PartialEq)]
pub struct Parcalar {
    pub scheme: String,
    pub netloc: String,
    pub path: String,
    pub query: String,
    pub fragment: String,
}

fn scheme_karakteri(c: char) -> bool {
    c.is_ascii_alphanumeric() || matches!(c, '+' | '-' | '.')
}

/// Python `urlsplit(url)`.
pub fn urlsplit(url: &str) -> Parcalar {
    // Python: bbas/son C0 kontrol ve bosluklari atar, tab/satir sonlarini siler.
    let temiz: String = url
        .trim_start_matches(|c: char| c <= ' ')
        .chars()
        .filter(|c| !matches!(c, '\t' | '\r' | '\n'))
        .collect();
    let mut p = Parcalar::default();
    let mut kalan = temiz.as_str();

    if let Some(i) = kalan.find(':') {
        let aday = &kalan[..i];
        let ilk_alfa = aday.chars().next().is_some_and(|c| c.is_ascii_alphabetic());
        if i > 0 && ilk_alfa && aday.chars().all(scheme_karakteri) {
            p.scheme = aday.to_ascii_lowercase();
            kalan = &kalan[i + 1..];
        }
    }
    if let Some(r) = kalan.strip_prefix("//") {
        let son = r.find(['/', '?', '#']).unwrap_or(r.len());
        p.netloc = r[..son].to_string();
        kalan = &r[son..];
    }
    if let Some(i) = kalan.find('#') {
        p.fragment = kalan[i + 1..].to_string();
        kalan = &kalan[..i];
    }
    if let Some(i) = kalan.find('?') {
        p.query = kalan[i + 1..].to_string();
        kalan = &kalan[..i];
    }
    p.path = kalan.to_string();
    p
}

/// Python `ParseResult.hostname`: userinfo ve port atilir, kucuk harfe indirilir.
pub fn hostname(netloc: &str) -> String {
    let hostinfo = match netloc.rfind('@') {
        Some(i) => &netloc[i + 1..],
        None => netloc,
    };
    let host = if let Some(r) = hostinfo.strip_prefix('[') {
        r.split(']').next().unwrap_or("")
    } else {
        hostinfo.split(':').next().unwrap_or("")
    };
    host.to_ascii_lowercase()
}

/// Python `urlunsplit` (netloc'lu http/https/ftp adresleri icin).
pub fn birlestir(p: &Parcalar) -> String {
    let mut url = String::new();
    if !p.scheme.is_empty() {
        url.push_str(&p.scheme);
        url.push(':');
    }
    if !p.netloc.is_empty() {
        url.push_str("//");
        url.push_str(&p.netloc);
        if !p.path.is_empty() && !p.path.starts_with('/') {
            url.push('/');
        }
    }
    url.push_str(&p.path);
    if !p.query.is_empty() {
        url.push('?');
        url.push_str(&p.query);
    }
    if !p.fragment.is_empty() {
        url.push('#');
        url.push_str(&p.fragment);
    }
    url
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ayristirma_python_ile_ayni() {
        let p = urlsplit("HTTPS://KULLANICI:sifre@X.com:8080/a/b?x=1#frag");
        assert_eq!(p.scheme, "https");
        assert_eq!(p.netloc, "KULLANICI:sifre@X.com:8080");
        assert_eq!(p.path, "/a/b");
        assert_eq!(p.query, "x=1");
        assert_eq!(p.fragment, "frag");
        assert_eq!(hostname(&p.netloc), "x.com");
    }

    #[test]
    fn magnet_semasi_netloc_almaz() {
        let p = urlsplit("magnet:?xt=urn:btih:ABC");
        assert_eq!(p.scheme, "magnet");
        assert_eq!(p.netloc, "");
        assert_eq!(p.query, "xt=urn:btih:ABC");
    }

    #[test]
    fn birlestir_bos_sorguyu_atar() {
        let p = urlsplit("https://x.com/a?");
        assert_eq!(birlestir(&p), "https://x.com/a");
    }
}
