//! Save-location categories, folder tree, last-folder preference and durable pending requests.
use afudm_types::{AfuError, Json, JsonMap, Result, Store};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::{
    collections::BTreeMap,
    fs::{self, DirEntry},
    io::Write,
    path::{Path, PathBuf},
    sync::{Mutex, MutexGuard},
};

const CATEGORIES: &[(&str, &str)] = &[
    (
        "video",
        "mp4,mkv,avi,mov,wmv,flv,webm,m4v,ts,mpg,mpeg,3gp,m3u8",
    ),
    ("muzik", "mp3,m4a,flac,wav,aac,ogg,opus,wma"),
    (
        "belge",
        "pdf,doc,docx,xls,xlsx,ppt,pptx,txt,epub,odt,csv,rtf",
    ),
    ("program", "exe,msi,apk,dmg,deb,rpm,appx,msix,bat"),
    ("arsiv", "zip,rar,7z,tar,gz,bz2,xz,iso,img,cab"),
    ("resim", "jpg,jpeg,png,gif,webp,bmp,svg,heic,tiff"),
];
fn extension(s: &str) -> Option<&str> {
    let (stem, ext) = s.rsplit_once('.')?;
    if !stem.is_empty() && plausible(ext) {
        Some(ext)
    } else {
        None
    }
}
fn plausible(ext: &str) -> bool {
    !ext.is_empty()
        && ext.chars().count() <= 8
        && ext.chars().all(char::is_alphanumeric)
        && !ext.chars().all(char::is_numeric)
}
fn url_path(url: &str) -> &str {
    let raw = url.split(['?', '#']).next().unwrap_or("");
    if let Some((_, hostpath)) = raw.split_once("://") {
        hostpath.find('/').map(|i| &hostpath[i..]).unwrap_or("")
    } else {
        raw
    }
}
pub fn kategori_tahmin(url: &str, tur: &str, dosya_adi: &str) -> String {
    if tur == "torrent" || url.to_lowercase().starts_with("magnet:") {
        return "torrent".into();
    }
    let path = url_path(url).to_lowercase();
    let part = path.rsplit('/').next().unwrap_or("");
    let ext = extension(dosya_adi)
        .map(str::to_lowercase)
        .or_else(|| extension(part).map(str::to_owned))
        .or_else(|| part.rsplit_once('.').map(|(_, s)| s.to_owned()))
        .unwrap_or_default();
    for (name, extensions) in CATEGORIES {
        if extensions.split(',').any(|e| e == ext) {
            return (*name).into();
        }
    }
    if tur == "video" {
        "video".into()
    } else {
        "genel".into()
    }
}
pub fn kategori_klasoru(ana: &str, kategori: &str) -> String {
    let dir = match kategori {
        "telefon" => "📱 Telefona İndir",
        "video" => "Video",
        "muzik" => "Müzik",
        "belge" => "Belgeler",
        "program" => "Programlar",
        "arsiv" => "Arşiv",
        "resim" => "Resimler",
        "torrent" => "Torrent",
        _ => "Genel",
    };
    Path::new(ana).join(dir).to_string_lossy().into_owned()
}
pub fn guvenli_dosya_adi(ad: &str) -> String {
    let mapped = ad
        .chars()
        .map(|c| {
            if c < ' ' || "<>:\"/\\|?*".contains(c) {
                '_'
            } else {
                c
            }
        })
        .collect::<String>();
    let mut clean = mapped
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .trim_end_matches(['.', ' '])
        .to_owned();
    let device = clean
        .split('.')
        .next()
        .unwrap_or("")
        .trim_end()
        .to_uppercase();
    if ["CON", "PRN", "AUX", "NUL"].contains(&device.as_str())
        || device
            .strip_prefix("COM")
            .or_else(|| device.strip_prefix("LPT"))
            .is_some_and(|s| s.len() == 1 && matches!(s.as_bytes()[0], b'1'..=b'9'))
    {
        clean.insert(0, '_')
    }
    if clean.chars().count() > 200 {
        if let Some(ext) = extension(&clean) {
            let n = 200usize.saturating_sub(ext.chars().count() + 1).max(1);
            clean = format!(
                "{}.{}",
                clean.chars().take(n).collect::<String>().trim_end(),
                ext
            )
        } else {
            clean = clean
                .chars()
                .take(200)
                .collect::<String>()
                .trim_end_matches(['.', ' '])
                .into()
        }
    }
    clean
}
fn visible(entry: &DirEntry) -> bool {
    let name = entry.file_name();
    let name = name.to_string_lossy();
    if name.starts_with(['$', '.']) || !entry.file_type().is_ok_and(|t| t.is_dir()) {
        return false;
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        return entry.metadata().is_ok_and(|m| m.file_attributes() & 6 == 0);
    }
    #[cfg(not(windows))]
    true
}
fn has_children(path: &Path) -> bool {
    fs::read_dir(path).is_ok_and(|r| {
        r.take(400)
            .filter_map(std::result::Result::ok)
            .any(|e| visible(&e))
    })
}
pub fn alt_klasorler(yol: &str, sinir: usize) -> Result<Vec<Json>> {
    let entries =
        fs::read_dir(yol).map_err(|e| AfuError::Invalid(format!("klasor okunamadi: {e}")))?;
    let mut out = Vec::new();
    for entry in entries {
        if out.len() >= sinir {
            break;
        }
        if let Ok(e) = entry {
            if visible(&e) {
                out.push(json!({"ad":e.file_name().to_string_lossy(),"yol":e.path().to_string_lossy(),"alt":has_children(&e.path())}));
            }
        }
    }
    out.sort_by_key(|r| r["ad"].as_str().unwrap_or("").to_lowercase());
    Ok(out)
}
pub fn klasor_olustur(ust: &str, ad: &str) -> Result<String> {
    let ad = guvenli_dosya_adi(ad);
    if ad.is_empty() {
        return Err(AfuError::Invalid("klasor adi bos".into()));
    }
    let path = Path::new(ust).join(ad);
    match fs::create_dir(&path) {
        Ok(()) => {}
        Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists && path.is_dir() => {}
        Err(e) => return Err(e.into()),
    };
    Ok(path.to_string_lossy().into_owned())
}
fn shell_folder(name: &str, fallback: &str) -> PathBuf {
    #[cfg(windows)]
    {
        use winreg::{enums::HKEY_CURRENT_USER, RegKey};
        if let Ok(key) = RegKey::predef(HKEY_CURRENT_USER)
            .open_subkey(r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        {
            if let Ok(value) = key.get_value::<String, _>(name) {
                let mut expanded = value;
                for (k, v) in std::env::vars() {
                    expanded = expanded.replace(&format!("%{k}%"), &v)
                }
                let path = PathBuf::from(expanded);
                if path.is_dir() {
                    return path;
                }
            }
        }
    }
    #[cfg(not(windows))]
    let _ = name;
    std::env::var_os("USERPROFILE")
        .or_else(|| std::env::var_os("HOME"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
        .join(fallback)
}
pub fn kisayollar(ana_indirme: &str, ag: &str) -> Vec<Json> {
    let candidates = [
        ("afudm", PathBuf::from(ana_indirme)),
        ("masaustu", shell_folder("Desktop", "Desktop")),
        (
            "indirilenler",
            shell_folder("{374DE290-123F-4565-9164-39C4925E467B}", "Downloads"),
        ),
        ("belgeler", shell_folder("Personal", "Documents")),
        ("videolar", shell_folder("My Video", "Videos")),
        ("muzik", shell_folder("My Music", "Music")),
    ];
    let mut out = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for (key, path) in candidates {
        if key == "afudm" && fs::create_dir_all(&path).is_err() {
            continue;
        }
        if path.is_dir() && seen.insert(path.to_string_lossy().to_lowercase()) {
            out.push(json!({"anahtar":key,"ad":path.file_name().unwrap_or_default().to_string_lossy(),"yol":path.to_string_lossy(),"alt":has_children(&path)}));
        }
    }
    for path in ag_konumlari(ag) {
        out.push(json!({"anahtar":"ag","ad":path.rsplit('\\').next().unwrap_or(&path),"yol":path,"alt":has_children(Path::new(&path))}));
    }
    #[cfg(windows)]
    for letter in b'A'..=b'Z' {
        let root = format!("{}:\\", letter as char);
        let wide = root.encode_utf16().chain(Some(0)).collect::<Vec<_>>();
        // SAFETY: wide is a NUL-terminated path and lives for the full call.
        let kind = unsafe { windows_sys::Win32::Storage::FileSystem::GetDriveTypeW(wide.as_ptr()) };
        if matches!(kind, 2..=4) && Path::new(&root).is_dir() {
            out.push(
                json!({"anahtar":"disk","ad":format!("{}:",letter as char),"yol":root,"alt":true}),
            );
        }
    }
    out
}
pub fn ag_yolu_mu(yol: &str) -> bool {
    yol.starts_with("\\\\")
}
pub fn ag_konumlari(ayar: &str) -> Vec<String> {
    let mut out = Vec::new();
    for row in ayar.lines() {
        let path = row.trim().trim_end_matches('\\');
        if !path.is_empty() && ag_yolu_mu(path) && !out.iter().any(|s| s == path) {
            out.push(path.into())
        }
    }
    out
}
pub fn ag_konumu_dogrula(yol: &str) -> Result<String> {
    let clean = yol.trim().trim_end_matches('\\');
    if clean.is_empty() {
        return Err(AfuError::Invalid("bos yol".into()));
    }
    if !ag_yolu_mu(clean) {
        return Err(AfuError::Invalid(
            "ag konumu \\\\sunucu\\paylasim biciminde olmali".into(),
        ));
    }
    if !Path::new(clean).is_dir() {
        return Err(AfuError::Invalid(
            "erisilemedi — paylasimi once Gezgin'den bir kez ac".into(),
        ));
    }
    Ok(clean.into())
}
/// app.py _coz_son_klasor: a remembered path belongs to a specific base directory.
pub fn son_klasor(store: &dyn Store, ana: &str) -> Result<String> {
    let value = store.get("son_klasor")?;
    Ok(value
        .filter(|v| v.is_object() && v["ana"] == ana)
        .and_then(|v| v["yol"].as_str().map(str::to_owned))
        .unwrap_or_default())
}
/// Call only after a successful download approval, as in app.py.
pub fn son_klasoru_hatirla(store: &dyn Store, ana: &str, secim: &JsonMap) -> Result<()> {
    if secim.get("folder_reset").is_some_and(crate::store::truthy) {
        store.set("son_klasor", json!(""))?;
    } else if secim.get("folder_edited").is_some_and(crate::store::truthy)
        && secim.get("dest_dir").is_some_and(crate::store::truthy)
    {
        store.set("son_klasor", json!({"yol":secim["dest_dir"],"ana":ana}))?;
    }
    Ok(())
}

#[derive(Clone, Serialize, Deserialize)]
struct Pending {
    istek: JsonMap,
    zaman: f64,
}
#[derive(Serialize, Deserialize)]
struct DiskRow {
    id: i64,
    istek: JsonMap,
    zaman: f64,
}
#[derive(Serialize, Deserialize)]
struct Disk {
    version: u64,
    items: Vec<DiskRow>,
}
struct State {
    items: BTreeMap<i64, Pending>,
    next: i64,
}
pub struct Bekleyenler {
    file: PathBuf,
    state: Mutex<State>,
}
const SECRETS: [&str; 3] = ["cookies", "headers", "user_agent"];
fn clean_expired(state: &mut State) {
    let threshold = crate::store::now() - Bekleyenler::SURE;
    for row in state.items.values_mut() {
        if row.zaman < threshold {
            for key in SECRETS {
                row.istek.remove(key);
            }
        }
    }
}
fn url_key(source: &str) -> String {
    let Some((scheme, rest)) = source.split_once("://") else {
        return source.into();
    };
    let scheme = scheme.to_lowercase();
    if !["http", "https", "ftp"].contains(&scheme.as_str()) {
        return source.into();
    }
    let rest = rest.split('#').next().unwrap_or("");
    let end = rest.find(['/', '?']).unwrap_or(rest.len());
    let (netloc, tail) = rest.split_at(end);
    let netloc = match netloc.rsplit_once('@') {
        Some((cred, addr)) => format!("{cred}@{}", addr.to_lowercase()),
        None => netloc.to_lowercase(),
    };
    let (path, query) = tail.split_once('?').unwrap_or((tail, ""));
    let query = if query.is_empty() {
        String::new()
    } else {
        format!("?{query}")
    };
    format!(
        "{scheme}://{netloc}{}{query}",
        if path.is_empty() { "/" } else { path }
    )
}
impl Bekleyenler {
    pub const SURE: f64 = 30.0 * 60.0;
    pub fn new(data: &Path) -> Result<Self> {
        let file = data.join("pending_downloads.json");
        let mut items = BTreeMap::new();
        match fs::read(&file) {
            Ok(bytes) => {
                let parsed = serde_json::from_slice::<Disk>(&bytes)
                    .ok()
                    .filter(|d| d.version == 1);
                let mut valid = parsed.is_some();
                if let Some(d) = parsed {
                    for r in d.items {
                        if r.id < 1
                            || items
                                .insert(
                                    r.id,
                                    Pending {
                                        istek: r.istek,
                                        zaman: r.zaman,
                                    },
                                )
                                .is_some()
                        {
                            valid = false;
                            break;
                        }
                    }
                }
                if !valid {
                    items.clear();
                    let stamp = std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .map_or(0, |d| d.as_nanos());
                    fs::rename(
                        &file,
                        data.join(format!("pending_downloads.json.corrupt-{stamp}")),
                    )?;
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e.into()),
        }
        let next = items
            .keys()
            .next_back()
            .copied()
            .unwrap_or(0)
            .checked_add(1)
            .ok_or_else(|| AfuError::Invalid("Invalid pending download".into()))?;
        Ok(Self {
            file,
            state: Mutex::new(State { items, next }),
        })
    }
    fn lock(&self) -> Result<MutexGuard<'_, State>> {
        self.state
            .lock()
            .map_err(|_| AfuError::Other("Bekleyen indirme kilidi kullanilamiyor.".into()))
    }
    fn save(&self, items: &BTreeMap<i64, Pending>) -> Result<()> {
        let rows = items
            .iter()
            .map(|(id, row)| {
                let mut req = row.istek.clone();
                for key in SECRETS {
                    req.remove(key);
                }
                DiskRow {
                    id: *id,
                    istek: req,
                    zaman: row.zaman,
                }
            })
            .collect();
        let parent = self
            .file
            .parent()
            .ok_or_else(|| AfuError::Io("Kayit klasoru bulunamadi.".into()))?;
        fs::create_dir_all(parent)?;
        let mut temp = tempfile::Builder::new()
            .prefix("pending-")
            .suffix(".tmp")
            .tempfile_in(parent)?;
        serde_json::to_writer(
            temp.as_file_mut(),
            &Disk {
                version: 1,
                items: rows,
            },
        )?;
        temp.flush()?;
        temp.as_file().sync_all()?;
        temp.persist(&self.file)
            .map_err(|e| AfuError::Io(e.error.to_string()))?;
        Ok(())
    }
    pub fn bak(&self, kimlik: i64) -> Result<Option<JsonMap>> {
        let mut state = self.lock()?;
        clean_expired(&mut state);
        Ok(state.items.get(&kimlik).map(|p| p.istek.clone()))
    }
    pub fn ekle(&self, istek: &JsonMap) -> Result<i64> {
        let mut state = self.lock()?;
        clean_expired(&mut state);
        if let Some(request) = istek.get("request_id").filter(|v| crate::store::truthy(v)) {
            if !request.as_str().is_some_and(|s| s.chars().count() <= 128) {
                return Err(AfuError::Invalid(
                    "Invalid download request identity".into(),
                ));
            }
            for (id, row) in &state.items {
                if row.istek.get("request_id") == Some(request) {
                    if row.istek.get("url") != istek.get("url") {
                        return Err(AfuError::Invalid(
                            "Download request identity conflicts with URL".into(),
                        ));
                    }
                    return Ok(*id);
                }
            }
        }
        if let Some(url) = istek
            .get("url")
            .and_then(Json::as_str)
            .filter(|u| !u.is_empty())
        {
            let key = url_key(url);
            for (id, row) in &state.items {
                if url_key(row.istek.get("url").and_then(Json::as_str).unwrap_or("")) == key {
                    return Ok(*id);
                }
            }
        }
        let id = state.next;
        state.next = state
            .next
            .checked_add(1)
            .ok_or_else(|| AfuError::Invalid("Invalid pending download".into()))?;
        let mut items = state.items.clone();
        items.insert(
            id,
            Pending {
                istek: istek.clone(),
                zaman: crate::store::now(),
            },
        );
        self.save(&items)?;
        state.items = items;
        Ok(id)
    }
    pub fn al(&self, kimlik: i64) -> Result<Option<JsonMap>> {
        let mut state = self.lock()?;
        let Some(row) = state.items.get(&kimlik).cloned() else {
            return Ok(None);
        };
        let mut items = state.items.clone();
        items.remove(&kimlik);
        self.save(&items)?;
        state.items = items;
        Ok(Some(row.istek))
    }
    pub fn geri_koy(&self, kimlik: i64, istek: &JsonMap) -> Result<()> {
        let mut state = self.lock()?;
        let mut items = state.items.clone();
        items.insert(
            kimlik,
            Pending {
                istek: istek.clone(),
                zaman: crate::store::now(),
            },
        );
        self.save(&items)?;
        state.items = items;
        Ok(())
    }
    pub fn ozet(&self) -> Result<Vec<Json>> {
        let mut state = self.lock()?;
        clean_expired(&mut state);
        Ok(state
            .items
            .iter()
            .map(|(id, row)| {
                let mut summary = JsonMap::new();
                summary.insert("id".into(), json!(id));
                for key in ["url", "title", "filename", "kind", "quality", "source"] {
                    summary.insert(
                        key.into(),
                        row.istek
                            .get(key)
                            .filter(|v| key == "url" || crate::store::truthy(v))
                            .cloned()
                            .unwrap_or(json!("")),
                    );
                }
                summary.insert(
                    "audio_only".into(),
                    json!(row
                        .istek
                        .get("audio_only")
                        .is_some_and(crate::store::truthy)),
                );
                json!(summary)
            })
            .collect())
    }
}
