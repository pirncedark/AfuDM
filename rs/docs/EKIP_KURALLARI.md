# AfuDM 3.0 Rust ekibi — ORTAK KURALLAR (her görevde geçerli)

## Yerler
- Rust çalışma alanı: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs  (cargo komutları BURADA)
- Python kaynağı (YALNIZ OKU, ASLA YAZMA): C:\Users\afuuu\Desktop\afuproject\AfuDM
  Bu klasörde kullanıcının commitlenmemiş işi var. Ona dokunma, orada test/derleme koşma.
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs altındaki Python dosyalarına da DOKUNMA; yalnız rs\ altında çalış.
- Benzer adlı kopyalar (AfuDM\_yedek, AfuDM\build_out, AfuDM_wt_*) referans DEĞİL.

## Sahiplik (çakışmayı önler)
- Her ekip YALNIZ kendi görev dosyasında listelenen dosyalara yazar. Başka dosya gerekiyorsa DUR, SONUC'ta sor.
- crates\afudm-types\src\lib.rs ve crates\afudm-core\src\lib.rs ile kök Cargo.toml'u YALNIZ Claude değiştirir.
  Sözleşmede eksik veya yanlış bir şey görürsen SONUC'a yaz; kendi kodunda geçici çözüm kullan.
- Yeni bağımlılık: yalnız KENDİ crate'inin Cargo.toml'una, sürüm yazarak ekle (`ureq = "3"`).
  `foo.workspace = true` kullanıyorsan, o paket kök Cargo.toml'da zaten olmalı.
- Cargo.lock ortak dosyadır; cargo onu kendisi günceller, elle düzenleme.

## Davranış eşitliği (en önemli kural)
- Python ne yapıyorsa Rust da aynısını yapar: aynı JSON alan adları, aynı varsayılanlar, aynı Türkçe hata metinleri, aynı dosya ve klasör adları.
- "İyileştirme" yapma. Python'da hata gördüğünde düzeltme; SONUC'a 📍 olarak yaz.
- Veri klasörü ve dosyaları (data\afudm.db, data\settings, api_token.txt, api_endpoint.json, aria2.session) aynı ad ve biçimde kalır. 2.9.x kullanıcısı güncelleme sonrası verisini kaybetmemeli.

## Kod
- Rust 2021, `cargo fmt`. `cargo clippy -p <crate> -- -D warnings` temiz olmalı.
- `unwrap()` ve `expect()` yalnız testlerde. Hatalar `afudm_types::AfuError` ile döner.
- Sırları (token, rpc-secret, çerez) log ya da hata metnine yazma.
- Her public fonksiyon için en az bir birim testi yaz. Python testlerinde (AfuDM\tests\) karşılığı olan durumları taşı.
- Ekranda pencere açma; testler headless çalışır.

## Git
YIKICI GIT YASAK: git restore / checkout -- / reset / clean / stash / rebase / amend / push / switch / commit.
Commit'i Claude atar.

## Bitirme ve SONUC
- Kendi crate'in için: `cargo build -p <crate>` + `cargo test -p <crate>` + `cargo clippy -p <crate> -- -D warnings`. Gerçek çıktının son 30 satırını SONUC'a yapıştır.
- SONUC dosyası: rs\docs\sonuc\SONUC_<EKIP>.md. İçinde: yazılan dosyalar, Python'dan taşınan fonksiyon listesi (✅ tamam / ⚠ eksik + neden), sözleşme sorunları, test çıktısı.
- "Bitti" demek için tüm `todo!()` gövdeleri dolu olmalı. Kalan varsa açıkça listele.
