use crate::{error, fault, merged, q, query, security, ApiCtx};
use afudm_types::{AfuError, Result};
use axum::{
    body::Body,
    extract::{Request, State},
    http::header,
    response::{IntoResponse, Response},
};
use futures_util::StreamExt;
use std::{
    path::{Path, PathBuf},
    time::Duration,
};
use tokio::io::AsyncWriteExt;

fn safe_name(raw: &str) -> String {
    let replaced = raw
        .chars()
        .map(|c| {
            if c < ' ' || "<>:\"/\\|?*".contains(c) {
                '_'
            } else {
                c
            }
        })
        .collect::<String>();
    let mut name = replaced
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .trim_end_matches(['.', ' '])
        .to_string();
    let stem = name
        .split('.')
        .next()
        .unwrap_or("")
        .trim_end()
        .to_uppercase();
    if ["CON", "PRN", "AUX", "NUL"].contains(&stem.as_str())
        || (stem.len() == 4
            && (stem.starts_with("COM") || stem.starts_with("LPT"))
            && (b'1'..=b'9').contains(&stem.as_bytes()[3]))
    {
        name.insert(0, '_');
    }
    if name.chars().count() > 200 {
        let extension = Path::new(&name)
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("");
        if extension.is_empty() {
            name = name.chars().take(200).collect()
        } else {
            let count = 200usize
                .saturating_sub(extension.chars().count() + 1)
                .max(1);
            name = format!(
                "{}.{}",
                name.chars().take(count).collect::<String>().trim_end(),
                extension
            );
        }
    }
    name
}
fn disposition(path: &Path, phone: bool) -> String {
    let name = path.file_name().unwrap_or_default().to_string_lossy();
    let encoded = url::form_urlencoded::byte_serialize(name.as_bytes())
        .collect::<String>()
        .replace('+', "%20");
    if phone {
        format!("attachment; filename*=UTF-8''{encoded}")
    } else {
        let ascii = name
            .chars()
            .filter(|c| c.is_ascii() && *c != '"' && *c != '\r' && *c != '\n')
            .collect::<String>();
        let ascii = if ascii.is_empty() {
            "indirilen_dosya"
        } else {
            &ascii
        };
        format!("attachment; filename=\"{ascii}\"; filename*=UTF-8''{encoded}")
    }
}
async fn stream_file(path: PathBuf, phone: bool) -> Response {
    let file = match tokio::fs::File::open(&path).await {
        Ok(file) => file,
        Err(_) => return fault(403, "ERISIM_ENGEL", "Erisim engellendi"),
    };
    let length = match file.metadata().await {
        Ok(meta) => meta.len(),
        Err(_) => return fault(500, "AKIS_HATASI", "Dosya aktarimi baslatilamadi"),
    };
    let mime = if phone {
        mime_guess::from_path(&path)
            .first_or_octet_stream()
            .to_string()
    } else {
        "application/octet-stream".into()
    };
    let mut response = Body::from_stream(tokio_util::io::ReaderStream::with_capacity(
        file,
        256 * 1024,
    ))
    .into_response();
    for (name, value) in [
        (header::CONTENT_TYPE, mime),
        (header::CONTENT_LENGTH, length.to_string()),
        (header::CONTENT_DISPOSITION, disposition(&path, phone)),
    ] {
        if let Ok(value) = value.parse() {
            response.headers_mut().insert(name, value);
        }
    }
    response
}
pub(crate) async fn download(State(ctx): State<ApiCtx>, req: Request) -> Response {
    file_response(ctx, req, false).await
}
pub(crate) async fn phone_download(State(ctx): State<ApiCtx>, req: Request) -> Response {
    file_response(ctx, req, true).await
}
async fn file_response(ctx: ApiCtx, req: Request, phone: bool) -> Response {
    let params = query(&req);
    let gid = q(&params, "gid");
    if gid.is_empty() {
        return fault(400, "GID_GEREKLI", "gid gerekli");
    }
    let path = if phone {
        // Python /dosya sirasi: aria2 tellStatus.files -> DB path.
        match ctx.manager.phone_download_path(gid) {
            Ok(path) => path,
            Err(e) => return error(e),
        }
    } else {
        match ctx.manager.resolve_item_path(gid) {
            Ok(path) => path,
            Err(e) => return error(e),
        }
    };
    let Some(path) = path else {
        return if phone {
            fault(404, "DOSYA_YOK", "dosya bulunamadi veya indirme bitmemis")
        } else {
            fault(404, "BULUNAMADI", "Dosya diskte yok veya hazir degil")
        };
    };
    let root = match ctx.manager.current_download_dir() {
        Ok(root) => root,
        Err(e) => return error(e),
    };
    if !security::path_inside(&path, Path::new(&root)) {
        return fault(403, "HEDEF_DISARIDA", "dosya indirme kokunun disinda");
    }
    if !path.is_file() {
        return if phone {
            fault(404, "DOSYA_YOK", "dosya bulunamadi veya indirme bitmemis")
        } else {
            fault(404, "BULUNAMADI", "Dosya diskte yok veya hazir degil")
        };
    }
    stream_file(path, phone).await
}
pub(crate) async fn add_blob(State(ctx): State<ApiCtx>, req: Request) -> Response {
    let length = req
        .headers()
        .get(header::CONTENT_LENGTH)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.parse::<u64>().ok());
    if length.is_some_and(|v| v > 512 * 1024 * 1024) {
        return fault(413, "DOSYA_BUYUK", "Dosya çok büyük; tarayıcıdan kaydedin.");
    }
    if length.is_none() || req.headers().contains_key(header::TRANSFER_ENCODING) {
        return blob_error();
    }
    let params = query(&req);
    let raw = params
        .get("filename")
        .map(String::as_str)
        .unwrap_or("download.png");
    if raw.is_empty()
        || [".", ".."].contains(&raw)
        || raw.chars().any(|c| "/\\:\0".contains(c))
        || params.keys().any(|k| k != "filename")
    {
        return blob_error();
    }
    let name = safe_name(raw);
    if name.is_empty() {
        return blob_error();
    }
    let root = match ctx.manager.current_download_dir() {
        Ok(v) => PathBuf::from(v),
        Err(_) => return blob_error(),
    };
    if tokio::fs::create_dir_all(&root).await.is_err() {
        return blob_error();
    }
    let root = match root.canonicalize() {
        Ok(v) => v,
        Err(_) => return blob_error(),
    };
    let mut target = None;
    for index in 0..10000 {
        let name = if index == 0 {
            name.clone()
        } else {
            let path = Path::new(&name);
            let stem = path.file_stem().unwrap_or_default().to_string_lossy();
            let ext = path
                .extension()
                .map(|v| format!(".{}", v.to_string_lossy()))
                .unwrap_or_default();
            format!("{stem} ({index}){ext}")
        };
        let path = root.join(name);
        match tokio::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&path)
            .await
        {
            Ok(file) => {
                target = Some((path, file));
                break;
            }
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(_) => return blob_error(),
        }
    }
    let Some((path, mut file)) = target else {
        return blob_error();
    };
    let mut remaining = length.unwrap_or(0);
    let mut stream = req.into_body().into_data_stream();
    let output: Result<_> = async {
        while let Some(chunk) = tokio::time::timeout(Duration::from_secs(30), stream.next())
            .await
            .map_err(|_| {
                AfuError::Invalid("Dosya aktarımı yarıda kaldı; yeniden indirin.".into())
            })?
        {
            let chunk = chunk.map_err(|_| {
                AfuError::Invalid("Dosya aktarımı yarıda kaldı; yeniden indirin.".into())
            })?;
            if chunk.len() as u64 > remaining {
                return Err(AfuError::Invalid("Dosya boyutu uygun degil".into()));
            }
            file.write_all(&chunk).await?;
            remaining -= chunk.len() as u64;
        }
        if remaining != 0 {
            return Err(AfuError::Invalid(
                "Dosya aktarımı yarıda kaldı; yeniden indirin.".into(),
            ));
        }
        file.flush().await?;
        drop(file);
        ctx.manager.add_completed_file(&path)
    }
    .await;
    match output {
        Ok(v) => merged(v),
        Err(_) => {
            let _ = tokio::fs::remove_file(&path).await;
            blob_error()
        }
    }
}
fn blob_error() -> Response {
    fault(
        400,
        "DOSYA_ALINAMADI",
        "Dosya alınamadı; tarayıcıdan yeniden indirin.",
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn windows_names_and_header_encoding() {
        assert_eq!(safe_name("CON.txt"), "_CON.txt");
        assert_eq!(safe_name("x?.png "), "x_.png");
        assert_eq!(safe_name("..."), "");
        assert!(disposition(Path::new("Türkçe.pdf"), false).contains("T%C3%BCrk%C3%A7e.pdf"));
    }
}
