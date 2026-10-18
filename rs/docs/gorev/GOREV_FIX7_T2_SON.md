# Entegrasyon-7: T2 tam koşusunda kalan 2 KALDI (bridge, network)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM
Son tam koşu: `python -B tests_hata\hepsi.py` → resources/fuzz/crash GECTI, bridge + network KALDI.
Raporlar: tests_hata\rapor\bridge_rows.json, tests_hata\rapor\network.json

## ÇALIŞACAĞIN DOSYALAR
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\tests_hata\scenarios.py, common.py, hepsi.py
- Uygulamada GERÇEK hata bulursan: yalnız C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app\src\yonetim.rs ya da crates\ altı, en fazla 30 satır; SONUC'ta ayrıca listele.
- docs\sonuc\SONUC_FIX7.md
Bu listenin dışındaki dosyaya yazma; başka dosya gerekiyorsa dur ve SONUC'ta sor.
YIKICI GIT YASAK: restore / checkout -- / reset / clean / stash / rebase / amend / push / switch / commit.
Kullanıcının AfuDM'ine (6810/6811), P\data, AfuDM.exe'ye DOKUNMA. Pencere açma. Kendi başlattığın python/aria2c süreçlerini sonunda kapat.

## 1. network: panel her iki tarafta ConnectionRefused (harness hatası olası)
📍 tests_hata\scenarios.py:352 `def network(apps)` — satır 359 `settings_save` ile `sunucu_port: pp` yazılıyor.
network.json: `opened` yanıtı py port 52381 (`zaten: True`), rs port 52434, ama `settings.sunucu_port` 56659 / 57387. Panel istekleri (loopback ve LAN, 8 durum) hepsi `ConnectionRefusedError`.
Hangi portun dinlendiğini bul. İkiye bölerek ara: önce `opened.port`'a doğrudan bir GET at; cevap varsa sorun harness'ın bağlandığı portta, yoksa panel açılışında.
`zaten:True` → panel common.py:83 `panelport` ile önceden açık olabilir; harness `opened.port`'u kullansın.
Rust ile Python farklı davranıyorsa SONUC'ta 📍 ile yaz.
Ek gözlem: network'teki settings içinde fuzz'dan kalma anahtarlar var (`url: javascript:alert(1)`, `dest_dir: ..\\escape_t2`, `gid: {}`, `action: 3`). settings_save bilinmeyen anahtarı iki tarafta da kabul ediyor (parite). Düzeltme yapma, SONUC'ta 📍 ile not et.

## 2. bridge: 7 satır şekil farkı — durum kirliliği + istisna eşdeğerliği
a) Durum kirliliği: bridge, crash testinin bıraktığı veriyle koşuyor. Rust tarafında crash öğeleri var, Python'da yok. Bu yüzden `snapshot`, `loglar` (gid null/string), `guncelleme_uygula` (rs: aktif iş var → `bekle/neden`; py: iş yok → `uygula` hata) farklı çıkıyor.
Çözüm: bridge (ve network) her iki taraf için TAZE ve özdeş veri klasörüyle başlasın, ya da iki tarafa aynı ön durum hazırlansın. Hangisi daha basitse.
b) İstisna eşdeğerliği: `reliability_recovery_preview [0]`, `reliability_restore [missing]`, `windows_integration_test [invalid-t2]` — Python `ValueError` fırlatıyor, Rust `{ok:false,error}` dönüyor.
UI'da (app\ui\app.js:170-172 `call()`) ikisi de aynı sonuca gidiyor: reject → toast(e.message). Karşılaştırmada "py exception" ile "rs ok:false + error string" EŞDEĞER sayılsın; uygulamayı değiştirme.
c) `reliability_diagnostics_preview`: rs ek `masked` anahtarı ve alt alan farkları var. Python P\app.py ilgili metodla karşılaştır. Gerçek fark varsa crates\afudm-extras\src\g1\ (reliability) içinde ≤30 satırla düzelt; yoksa nedenini yaz.

## Kontrol (gerçek çıktıyı SONUC'a yapıştır)
1. `python -B tests_hata\hepsi.py --only bridge` ve `--only network` → GECTI
2. Ardından tam koşu `python -B tests_hata\hepsi.py` → 5 RESULT satırının hepsi GECTI (crash'te Python KALDI satırları beklenir, toplam crash GECTI kalmalı).
3. Uygulama kodu değiştiyse: `cargo test` + `cargo clippy --all-targets -- -D warnings` + `cargo clippy --manifest-path app\Cargo.toml -- -D warnings` yeşil.
SONUC: docs\sonuc\SONUC_FIX7.md. Soru sorup durma.
