use super::*;
use crate::tests::{aria_binary, serve_bytes};
use std::cell::Cell;

#[test]
fn download_checksum_failure_and_invalid_binary_preserve_existing_engine() {
    let tmp = tempfile::tempdir().unwrap();
    fs::create_dir(tmp.path().join("engine")).unwrap();
    let target = tmp.path().join("engine/cloudflared.exe");
    fs::write(&target, b"existing installation").unwrap();
    let (port, server) = serve_bytes(200, b"bad checksum".to_vec());
    let progress = Cell::new((0, 0));
    let err = install(
        tmp.path(),
        &MOTORLAR[3],
        &format!("http://127.0.0.1:{port}/"),
        &|a, b| progress.set((a, b)),
    )
    .unwrap_err();
    assert_eq!(
        err.to_string(),
        "cloudflared.exe SHA-256 dogrulamasi basarisiz"
    );
    assert_eq!(progress.get(), (12, 12));
    server.join().unwrap();
    assert_eq!(fs::read(&target).unwrap(), b"existing installation");
    let (port, server) = serve_bytes(200, b"not an executable".to_vec());
    let err = install(
        tmp.path(),
        &MOTORLAR[1],
        &format!("http://127.0.0.1:{port}/"),
        &|_, _| {},
    )
    .unwrap_err();
    assert_eq!(
        err.to_string(),
        "yt-dlp.exe indi ama calismadi (bozuk indirme?)"
    );
    server.join().unwrap();
    assert!(!tmp.path().join("engine/yt-dlp.exe").exists());
}

#[test]
fn download_extracts_only_named_zip_member_and_validates_executable() {
    let tmp = tempfile::tempdir().unwrap();
    let bytes = fs::read(aria_binary()).unwrap();
    let mut writer = zip::ZipWriter::new(std::io::Cursor::new(Vec::new()));
    writer
        .start_file(
            "package/aria2c.exe",
            zip::write::SimpleFileOptions::default(),
        )
        .unwrap();
    writer.write_all(&bytes).unwrap();
    let archive = writer.finish().unwrap().into_inner();
    let (port, server) = serve_bytes(200, archive);
    let result = install(
        tmp.path(),
        &MOTORLAR[0],
        &format!("http://127.0.0.1:{port}/"),
        &|_, _| {},
    )
    .unwrap();
    server.join().unwrap();
    assert_eq!(result["ad"], "aria2c");
    assert_eq!(
        fs::read(tmp.path().join("engine/aria2c.exe")).unwrap(),
        bytes
    );
    assert!(result["boyut_mb"].as_f64().unwrap() > 0.0);
    assert!(yol(tmp.path(), "aria2c").unwrap().is_file());
    let mut writer = zip::ZipWriter::new(std::io::Cursor::new(Vec::new()));
    writer
        .start_file("wrong.exe", zip::write::SimpleFileOptions::default())
        .unwrap();
    writer.write_all(b"x").unwrap();
    let (port, server) = serve_bytes(200, writer.finish().unwrap().into_inner());
    let err = install(
        tmp.path(),
        &MOTORLAR[0],
        &format!("http://127.0.0.1:{port}/"),
        &|_, _| {},
    )
    .unwrap_err();
    server.join().unwrap();
    assert_eq!(err.to_string(), "zip icinde aria2c.exe bulunamadi");
    assert_eq!(
        fs::read(tmp.path().join("engine/aria2c.exe")).unwrap(),
        bytes
    );
}

#[test]
fn sha256_successfully_verified_before_installing_direct_binary() {
    let tmp = tempfile::tempdir().unwrap();
    let bytes = fs::read(aria_binary()).unwrap();
    let digest = format!("{:x}", Sha256::digest(&bytes));
    let m = Motor {
        sha256: Some(Box::leak(digest.into_boxed_str())),
        ..MOTORLAR[1]
    };
    let (port, server) = serve_bytes(200, bytes.clone());
    install(
        tmp.path(),
        &m,
        &format!("http://127.0.0.1:{port}/"),
        &|_, _| {},
    )
    .unwrap();
    server.join().unwrap();
    assert_eq!(
        fs::read(tmp.path().join("engine/yt-dlp.exe")).unwrap(),
        bytes
    );
    assert!(!tmp.path().join("engine/yt-dlp.exe.eski").exists());
}
