# Ekip G2: Eklenti sistemi, çerez, link toplayıcı, kurallar (claude kod ajanı)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM

## ÇALIŞACAĞIN DOSYALAR
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-extras\src\g2\ (mod.rs ve alt dosyalar)
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-extras\Cargo.toml: yalnız [dependencies] sonuna satır ekle
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_G2.md
DOKUNMA: extras\src\lib.rs, g1\, h\, afudm-core, afudm-api.

## Python kaynağı
📍 P\core\eklenti.py (1112) + P\core\eklenti_host.py (168): eklenti kurma, kaldırma, izinler, sha256 doğrulama, etkinleştirme, günlük.
   - Depo: store.eklenti_*. Rotalar: /eklenti, /eklenti/gunluk, /eklenti/islem, /eklentiler.
   - eklenti_host.py'yi oku: eklentiler ayrı süreçte mi çalışıyor? Çalışıyorsa Python eklentisini çalıştırmak Python yorumlayıcısı ister. Çözemiyorsan seçenekleri SONUC'ta yaz (ör. liste ve kurulum çalışsın, eklenti çalıştırma 3.1'e kalsın). Uydurma çözüm yapma.
📍 P\core\cerez.py (129): tarayıcı çerezlerini aria2/yt-dlp için hazırlama. Çerez değerleri gizli kalmalı.
📍 P\core\linkgrabber.py (387): metinden link çıkarma, süzme, probe. Rota /linkgrabber; app.py linkgrabber_* (505–610).
📍 P\core\rules.py (43): kural motoru. Depo: store.rules_list / rules_save; rota /rules; app.py rules_simulate, download_rules.
HTTP rotaları g2::router(ctx) içinde olsun; yanıt biçimi P\api\server.py ile birebir.
Arayüz karşılıklarını g2'de `pub fn` olarak ver (F ekibi bağlayacak).
Testler: P\tests\eklenti_test.py, eklenti_debug_duzeltme_test.py, cerez_test.py, cerez_session_test.py, linkgrabber_test.py karşılıkları.

## Bitiş
- `cargo test -p afudm-extras` ve clippy (-D warnings) çıktısı SONUC'ta olsun.
