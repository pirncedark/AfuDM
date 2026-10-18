# CI ve Rust sürüm betikleri

| Betik | İş |
|---|---|
| `surum_oku.py` | `rs/Cargo.toml` workspace sürümünü okur. Python 3.11+ gerekir. |
| `aria2_indir.py` | CI için resmi aria2c motorunu `engine/` altına indirir. |
| `build_release_rust.ps1` | Rust exe derler, sürümleri eşler, taşınabilir paket hazırlar. |
| `verify_release.ps1` | Rust zip yollarını, gerekli dosyaları, win64 PE ve ürün sürümünü denetler. |
| `smoke_test.ps1` | Rust paketini doğrular; kullanıcı uygulamasını başlatmaz. |
| `make_checksums.ps1` | Paket için SHA-256 üretir. |

Yerel kontroller: `cargo test --manifest-path rs/Cargo.toml`, `cargo test --manifest-path rs/app/Cargo.toml`, `python -m pytest tests -q`.
Eski Python paketleme hattı `python-arsiv-3.0.1` etiketinde arşivlendi.
