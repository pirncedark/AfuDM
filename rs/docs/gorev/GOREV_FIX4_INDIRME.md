# Entegrasyon-4: HTTP indirme doğruluğu ve snapshot (claude kod ajanı)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Test raporu: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_T1.md (ikinci tur) ve tests_parity\rapor\sonuc_son.json
Uyum testi: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\tests_parity\uyum_testi.py (README'ye bak)
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM

## ÇALIŞACAĞIN DOSYALAR
- crates\afudm-core\src\queue.rs ve queue\ alt modülleri
- crates\afudm-engine\src\
- crates\afudm-api\src\ (yalnız 3. madde)
- tests_parity\ (yalnız hata ayıklama için senaryo ekleme; harness mantığını bozma)
- docs\sonuc\SONUC_FIX4.md
DOKUNMA: app\ (F4a ve F4b çalışıyor), afudm-types, afudm-core\src\lib.rs.

## Hata arama yöntemi (kullanıcı kuralı): ikiye bölerek ara
Akışın ORTASINDAN başla, her adımda tek ve ucuz bir kontrol yap, sonucu kanıt olarak yaz:
/add → aria2 addUri seçenekleri → aria2'nin yazdığı dosya → tamamlanma → DB satırı → snapshot → /indir.

## Sorunlar
1. KRİTİK (5.3d): Rust tarafında indirilen a.bin kaynakla aynı değil; Python'da aynı. Aynı yerel HTTP dosyası kullanılıyor.
   - Rust'ın aria2'ye verdiği seçenekleri Python'unkiyle karşılaştır: split, min-split-size, header, out, dir, continue, allow-overwrite, file-allocation.
   - Dosyanın boyutuna ve içeriğine bak: eksik mi, sıfır dolgulu mu (falloc), başka bir dosya mı, `.aria2` hâlâ duruyor mu (tamamlanmadan mı ölçüldü)?
   - Kök nedeni bul ve düzelt. Kanıt: aynı senaryoda SHA-256 eşit.
2. KRİTİK (5.1, 5.3, 5.6, 9.2, 9.3): Tamamlanan indirme iki tarafta da /snapshot'ta görünmüyor, /indir ve /share_create 404 veriyor.
   - Python log'u gid'in tamamlanınca aria2'den düştüğünü gösteriyor (`GID ... is not found`).
   - Python snapshot tamamlanan işleri DB'den hangi koşulla veriyor? (manager.py snapshot 1695–1878, DB satırı status alanı, history ve limit.) Harness yanlış yere bakıyor olabilir. Önce Python'da hangi istekle tamamlanan satırın görüldüğünü kanıtla.
   - Python gerçekten göstermiyorsa harness'ı Python davranışına göre düzelt (ör. satırı /snapshot'ın başka anahtarında ya da gid değişimiyle ara). Python gösteriyor ama Rust göstermiyorsa Rust'ı düzelt.
   - Hedef: 5.x ve 9.2–9.3 adımları iki tarafta da gerçek dosyayla geçsin (/indir gövdesi = kaynak dosya).
3. KRİTİK (4.2): /control resume. Python 500, Rust 200 dönüyor (📍 crates\afudm-api\src\lib.rs control ≈370). Python neden 500 dönüyor? Senaryodaki durumu Python'da gerçekten üret. Python davranışı bir hata ise (ör. duraklatılmamış işi resume etmek) yine Python'u taklit et, ama SONUC'ta 📍 olarak işaretle.

## Kontrol
- Uyum testini tam koş: `python tests_parity\uyum_testi.py`. Rust exe'yi kendin derle (`cargo build --release --manifest-path app\Cargo.toml`). F4a/F4b de aynı anda derleyebilir; kilit beklemesi normaldir. Harness exe'yi kopyalıyor.
- Hedef: kritik = 0. Kalan her farkı gerekçesiyle yaz.
- `cargo test -p afudm-core -p afudm-engine -p afudm-api` + clippy yeşil.
- Kullanıcının 6811 AfuDM'ine ve P\data'ya dokunma. Pencere açma. Test sonunda süreçleri kapat.
SONUC: docs\sonuc\SONUC_FIX4.md. Soru sorup durma.
