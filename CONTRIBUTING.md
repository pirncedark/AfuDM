# Contributing to AfuDM

Contributions are welcome. Please keep changes focused, run the relevant offline checks, and use Conventional Commit messages such as `fix:`, `docs:`, or `ci:`.

## Geliştirme ve gönderim

Geliştirme dalında çalışın, değişiklikleri commit kancalarıyla kaydedin, `git pull --rebase` ile güncel kalın ve ardından push edin. Push öncesi yerel test kancası çalışır. Pull request açın, CI'ın yeşil olmasını bekleyin ve squash merge kullanın. Sürüm PR'ını Release Please oluşturur; exe derleme ve GitHub Release mevcut `release.yml` akışında kalır.

Kancaları kurmak ve gönderim sırasını görmek için [`docs/PUSH_SIRASI.md`](docs/PUSH_SIRASI.md) dosyasını izleyin.

## Yerel doğrulama

Rust ürünü: `cargo test --manifest-path rs/Cargo.toml` ve `cargo test --manifest-path rs/app/Cargo.toml`. Sürüm araçları: `python -m pytest tests -q`. Python 3.11+ yalnız test ve sürüm araçları içindir; masaüstü uygulama Rust/Tauri ile çalışır. Push öncesi kancalar iki Rust workspace testini çalıştırır.
