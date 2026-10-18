# Ekip F4a ve F4b: Köprünün son kalan komutları (iki claude kod ajanı, paralel)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Kalan liste: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_F3.md, "Madde 3 — henüz yok" bölümü
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM; arayüz metotları P\app.py `class Api` içinde.

Köprü yapısı: app\src\bridge.rs `dispatch` bilinmeyen adı önce `crate::kopru_g::dispatch`, sonra `crate::kopru_h::dispatch` fonksiyonuna verir. Her ekip YALNIZ kendi dosyasına yazar.
Yardımcıları (Kabuk, ctx_cagri, s(), hata(), motor_hazir_degil...) bridge.rs'ten kullan. Gerekirse onları `pub(crate)` yap; bridge.rs'te bunun dışında bir şey değiştirme.
Her komutun yanıtı Python Api metodunun döndürdüğü dict ile birebir aynı olmalı.

## F4a → app\src\kopru_g.rs
- add_links (P\core\servis.py ekle, kısmi başarı raporu). En kritik komut, arayüzün ana "ekle" akışı. Python'daki gibi her link için manager.add.
- linkgrabber_analiz / suz / iptal / onceki / probe / ekle (app.py 505–610). Çekirdek mantık Rust'ta HAZIR: crates\afudm-extras\src\g2\linkgrabber.rs. Onu kullan.
- rules_save, rules_simulate, download_rules (g2\kurallar.rs)
- cerez (g2\cerez.rs), chrome_* (g1\chrome.rs)
- eklenti_kur / incele / guncelle / kaldir / ayar_kaydet / gunluk / islem: g2 eklenti servisi. Kabuktaki TEK servis örneğini kullan; boot.rs'te nasıl oluşturulduğuna bak.
- probe, proxy_testi, port_durumu, ayar_rozetleri, defender_scan

## F4b → app\src\kopru_h.rs
- sunucu_* (durum / ayarla / anahtar / istemci / profil): P\core\erisim.py + afudm-api erisim modülü
- start_pairing, telefon_*: crates\afudm-extras\src\h\esleme.rs
- share_*, dosya_sec_ve_paylas, agda_paylas: h\paylasim.rs, h\smb.rs
- loglar dışındaki olay sorguları, ve app.py Api'de olup hâlâ HİÇBİR yerde bağlı olmayan diğer metotlar (F4a'nın listesi dışında kalanlar)

## İkisi için ortak
- Bitince şu kontrolü koş: app.py Api'deki public metot adları ile bridge.rs + kopru_g.rs + kopru_h.rs içindeki adları karşılaştıran küçük bir python betiği (scratch klasöründe). Sonucu SONUC'a yapıştır. Senin listendeki bir ad hâlâ yoksa bitmiş sayılmaz.
- `cargo clippy --manifest-path app\Cargo.toml -- -D warnings` ve `cargo build --release --manifest-path app\Cargo.toml` yeşil olmalı. Diğer ekip aynı anda derliyor olabilir; kilit beklemesi normaldir.
- Pencere AÇMA. Canlı test 6811 dışı portla ve izole kopyayla yapılsın; test bitince süreçleri kapat.
- SONUC: docs\sonuc\SONUC_F4a.md ya da SONUC_F4b.md. Soru sorup durma.
