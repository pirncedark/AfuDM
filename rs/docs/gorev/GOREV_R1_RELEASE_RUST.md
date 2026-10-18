# R1: Yayın hattını Rust exe'ye çevir (codex)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Öneri (T2, uygulanmadı): C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_T2.md satır 231-243 "Release iş akışı önerisi"
Repo kökü (worktree, dal feat/rust-tauri): C:\Users\afuuu\Desktop\afuproject\AfuDM_rs
DOKUNMA: C:\Users\afuuu\Desktop\afuproject\AfuDM (kullanıcının ana kopyası), oradaki data\ ve çalışan AfuDM.exe, portlar 6810/6811. Pencere açma.
YIKICI GIT YASAK: restore / checkout -- / reset / clean / stash / rebase / amend / push / switch / commit.

## ÇALIŞACAĞIN DOSYALAR (hepsi C:\Users\afuuu\Desktop\afuproject\AfuDM_rs altında)
- .github\workflows\release.yml (📍 satır 67-78: pip + PyInstaller; satır 80-84: build_release.ps1; satır 86-96: zip/verify/smoke/checksum)
- .github\workflows\ci.yml ve .github\workflows\quality-gate.yml (yalnız Rust işi EKLE; Python işlerini silme)
- scripts\build_release_rust.ps1 (YENİ)
- scripts\verify_release.ps1, scripts\smoke_test.ps1 (Rust paketine uyarla; Python paketi kontrolü gerekiyorsa parametreyle ayır)
- release-please-config.json (extra-files), rs\Cargo.toml satır 14 `version = "3.0.0"`, rs\app\Cargo.toml satır 7 `version = "3.0.0"`, rs\app\tauri.conf.json (version alanı varsa)
- rs\docs\sonuc\SONUC_R1.md
Bu listenin dışındaki dosyaya yazma; başka dosya gerekiyorsa dur ve SONUC'ta sor.

## Yapılacaklar
1. Paket düzeni 2.9.x güncelleyicisiyle AYNI kalmalı: `AfuDM-v<surum>-win64.zip` içinde kök klasör `AfuDM\`, içinde `AfuDM.exe` + çalışması için gereken her şey (engine\aria2c.exe vb.). Rust exe'nin motorları ve UI'yi nereden okuduğunu kodda bul (rs\app\src\boot.rs, rs\crates\afudm-engine) ve pakete yalnız gerekenleri koy. Kullanıcı data klasörü pakete girmez. 2.9.x'in eski Python paketindeki ek dosyalardan (_internal\ vb.) hangilerinin artık gereksiz olduğunu SONUC'ta listele.
   T2 provası: P\core\guncelleme.py bu zip'i açıp exe'yi değiştirebildi (SONUC_T2 bölüm 3). Bu düzeni bozma.
2. scripts\build_release_rust.ps1: `cargo build --release --locked --manifest-path rs\app\Cargo.toml` (test-kapisi özelliği KAPALI) → build_out\paket\AfuDM\ staging → release.yml'nin beklediği yollar (build_out\AfuDM-v$surum-win64.zip, build_out\paket\AfuDM\AfuDM.exe).
3. release.yml: PyInstaller ve pip pywebview adımlarını Rust derlemesiyle değiştir. Sabit sürümlü Rust araç zinciri (dtolnay/rust-toolchain veya rustup, sürüm sabitli; action'lar SHA ile sabitlenmiş olsun, dosyadaki mevcut kalıba uy). Cargo önbelleği serbest. Tag/main/gate kontrolleri, checksum, sürüm notu SHA doldurma, yayın adımları AYNEN kalsın.
   Sürüm kapısı: tag sürümü = core\surum.py = rs\Cargo.toml = rs\app\Cargo.toml (= tauri.conf.json varsa) olmalı; değilse iş dursun.
   `scripts/test.ps1` (Python + eklenti testleri) kalsın; ek olarak rs için `cargo test` + `cargo clippy -D warnings` (kök workspace ve rs\app).
4. release-please-config.json extra-files'a rs\Cargo.toml ve rs\app\Cargo.toml (ve tauri.conf.json) ekle; release-please bunları güncelleyebilsin (generic updater için `# x-release-please-version` işaretini o satırlara ekle ya da toml tipi jsonpath kullan; release-please belgesini context7 ile doğrula).
5. ci.yml / quality-gate.yml: PR'da rs için fmt --check, test, clippy -D warnings işi ekle (windows-latest). Mevcut Python işlerini değiştirme.
6. Yerel prova (internet yok sayılabilir, cargo offline önbellek var): build_release_rust.ps1'i çalıştır → zip üret → verify_release.ps1 ve smoke_test.ps1'i bu zip'le geçici klasörde, izole veri ve 6811 olmayan portla, penceresiz koş. Gerçek çıktıyı SONUC'a yapıştır.
   YAML sözdizimini doğrula (python -c "import yaml,sys;yaml.safe_load(open(...))").

SONUC: rs\docs\sonuc\SONUC_R1.md — değişen dosyalar, prova çıktısı, açık riskler. Soru sorup durma.
