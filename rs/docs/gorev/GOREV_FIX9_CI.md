# FIX9: PR #122 CI kırmızıları (codex)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Repo kökü: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs (dal feat/rust-tauri, PR https://github.com/pirncedark/AfuDM/pull/122)
YIKICI GIT YASAK: restore / checkout -- / reset / clean / stash / rebase / amend / push / switch / commit. Pencere açma. C:\Users\afuuu\Desktop\afuproject\AfuDM'ye ve kullanıcının AfuDM'ine (6810/6811) DOKUNMA.

## ÇALIŞACAĞIN DOSYALAR
- rs\crates\afudm-db\src\tests.rs
- tests\release_tools_test.py
- rs\app\ui\app.js, rs\app\ui\i18n.js
- rs\docs\sonuc\SONUC_FIX9.md
Başka dosya gerekiyorsa dur ve SONUC'ta sor.

## Hatalar (CI logları)
1. 📍 rs\crates\afudm-db\src\tests.rs:21 `real_database_byte_copy_preserves_python_table_counts` CI'da panik: "Source database was not available to copy". Test, kullanıcının gerçek DB'sine bağlı; CI'da bu DB yok.
   Kaynak DB yoksa test atlansın: erken `return` ile birlikte eprintln ile "atlandı" yazsın, ya da `#[ignore]` + açıklama. Yerelde DB varsa test eskisi gibi çalışsın.
2. 📍 tests\release_tools_test.py:10 `test_ci_workflows_build_pyinstaller_before_packaging` hata veriyor: release.yml artık PyInstaller değil, Rust derliyor (scripts\build_release_rust.ps1).
   Testi yeni hatta göre güncelle. Aynı amacı korusun: paketlemeden önce exe derleniyor mu (cargo build --release ... → build_release_rust.ps1 sırası). Hatayı görmek için: `python -B tests\release_tools_test.py`.
3. CodeQL (2 yüksek): `js/xss-through-dom` "DOM text reinterpreted as HTML"
   - 📍 rs\app\ui\app.js:896
   - 📍 rs\app\ui\i18n.js:1818
   Bu UI, Python sürümündeki ui\app.js ve ui\i18n.js'nin kopyası. Aynı satırların main'deki hâline bak (`git show origin/main:ui/app.js`, `git show origin/main:ui/i18n.js`): orada nasıl çözülmüş ya da işaretlenmemişse aynısını uygula. Gerekirse innerHTML yerine textContent ya da güvenli DOM kurulumu kullan; davranış değişmesin.
   Değişiklikten sonra `npm`/node testleri varsa koş (scripts\test.ps1 içindeki UI testleri; pencere açmayan kısımlar).

## Kontrol (gerçek çıktıyı SONUC'a yapıştır)
- `cargo test --manifest-path rs\Cargo.toml -p afudm-db`
- `python -B tests\release_tools_test.py`
- `powershell -ExecutionPolicy Bypass -File scripts\test.ps1` (ya da CI'nin "offline" işinin koştuğu komut; .github\workflows\ci.yml'de bak)
- `cargo fmt --manifest-path rs\Cargo.toml --all -- --check`
SONUC: rs\docs\sonuc\SONUC_FIX9.md. Soru sorup durma.
