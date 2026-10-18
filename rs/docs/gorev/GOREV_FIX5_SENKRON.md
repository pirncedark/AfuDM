# Entegrasyon-5: aria2 senkron döngüsü + /dosya + uyum testi (codex)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Önceki rapor (oku, kanıtlar orada): C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_FIX4.md
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM

## ÇALIŞACAĞIN DOSYALAR
- crates\afudm-core\src\queue.rs ve queue\ alt modülleri
- crates\afudm-api\src\transfer.rs
- app\src\izleme.rs, app\src\boot.rs (yalnız senkron döngüsünü başlatmak için)
- tests_parity\uyum_testi.py (yalnız 1. madde: ortam sorunu)
- docs\sonuc\SONUC_FIX5.md
YIKICI GIT YASAK: restore / checkout -- / reset / clean / stash / rebase / amend / push / switch / commit.

## Yapılacaklar
1. Ortam: uyum testinin 3. koşusunda iki tarafta da indirme 150 sn'de tamamlanmadı (5.1 satir_yok). Önce bunu bul: yerel dosya sunucusu ayakta mı, port çakışması var mı (kullanıcının aria2'si 6810'da, AfuDM'i 6811'de; onlara DOKUNMA), harness'ın başlattığı aria2 hangi portta. Testi tekrarlanabilir hale getir: iki ardışık koşu aynı sonucu vermeli.
2. KRİTİK 5.2: Python tamamlanan işi aria2'den değil DB satırından gösteriyor (`_shape_row`, start_after dahil), çünkü remove/save_session sırasında `aria2.purgeDownloadResult` çağrılıyor (P\core\manager.py 886–990, P\core\daemon.py 258–263).
   Rust'ta tamamlanma yalnız snapshot yoklamasında işleniyor (queue\shaping.rs `known_complete`). Purge eklenince tamamlanma kaybolup 22 kritik fark çıktı.
   Çözüm: Python'daki `_sync_aria2` (ve onu çağıran arka plan döngüsü) eşdeğerini core'a ekle, ör. `pub fn sync_aria2(m:&Manager) -> Result<()>`. Tamamlanan / hatalı işleri DB'ye yazsın, `queue::tamamlandi` zincirini çağırsın, ardından Python'un purge yaptığı noktalarda purge etsin.
   app\src\izleme.rs bu fonksiyonu Python'daki aralıkla çağırsın. Snapshot artık tamamlanmayı işlemesin, yalnız okusun. Motor uykudaysa döngü motoru UYANDIRMASIN (IdleRpc sleeping kontrolü).
3. KRİTİK 5.6: 📍 crates\afudm-api\src\transfer.rs `phone_download` yalnız DB `path` alanını okuyor. Python ilk adımda aria2 `tellStatus.files[0].path`'e bakıyor, sonra DB'ye. Python'daki sırayı birebir uygula. Python bu senaryoda da 404 veriyorsa senaryoyu Python'un 200 verdiği bir duruma çevir (harness) ve iki tarafı orada karşılaştır.
4. Kontrol: `cargo test -p afudm-core -p afudm-api -p afudm-engine`, clippy -D warnings, `cargo build --release --manifest-path app\Cargo.toml`.
   Ardından uyum testini İKİ KEZ koş (`python tests_parity\uyum_testi.py`). Hedef: iki koşuda da kritik = 0.
   Kalan orta ve kozmetik farkları gerekçesiyle listele.
SONUC: docs\sonuc\SONUC_FIX5.md, gerçek çıktılarla. Soru sorup durma. Kullanıcının çalışan AfuDM'ine ve P\data'ya dokunma, pencere açma, süreçlerini kapat.
