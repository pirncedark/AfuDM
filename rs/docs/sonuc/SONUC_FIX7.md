# SONUC FIX7 — T2 son: bridge + network KALDI kapatma

## Değişen dosyalar (yalnız izinli dosyalar)
- `tests_hata\hepsi.py:24-38` — bridge ve network için her koşuda taze, özdeş veri klasörüyle yeni `App` çifti (`fresh()` sarmalayıcı). Önceki asamalardan (crash/fuzz) kalan durum bridge'e taşınmıyordu (snapshot, loglar, guncelleme_uygula sapmaları).
- `tests_hata\scenarios.py:361-362` — `network()`: `sunucu_ayarla` yanıtındaki gerçek panel portu (`opened.port`) kullanılıyor; `pp` (settings'e yazılan port) yerine. Panel `zaten:True` ile önceki portta açık kalabiliyordu; istekler ConnectionRefused alıyordu.
- Uygulama kodu (`app\src\yonetim.rs`, `crates\`) DEĞİŞMEDİ; cargo kontrolü gerekmiyor.

## Ek gözlemler (📍, düzeltilmedi)
- network: `settings` içindeki fuzz kalıntısı anahtarlar (`url: javascript:alert(1)`, `dest_dir: ..\\escape_t2`, `gid: {}`, `action: 3`) iki tarafta da kabul ediliyor (parite). Düzeltme yapılmadı.
- bridge: `reliability_recovery_preview [0]`, `reliability_restore [missing]`, `windows_integration_test [invalid-t2]` — Python ValueError, Rust `{ok:false,error}`; görev kuralına göre `muaf` (eşdeğer) işaretli.
- bridge: `reliability_diagnostics_preview` anahtar kümeleri iki tarafta eşit (`masked` üst düzeyde iki tarafta da var); gerçek fark yok, kod değişmedi.
- fuzz (harness dışı, uygulama davranışı, izin dosyası dışı): 29-30 fark — `/reliability/backup|integrity|diagnostics-*` ve `/windows-integration` rotalarında bozuk JSON / liste gövdesinde Python 400, Rust 200. Bu bir parite açığı olabilir; düzeltme için uygulama kodu izni ve karar gerekiyor.
- fuzz flake: bir önceki tam koşuda `/add huge` için Python ConnectionAbortedError (1 disconnect) görüldü; bu koşuda 0. Tekrar eden bir durum mu, izlenmeli.

## Koşu sonuçları
Önceki (düzeltme öncesi) tam koşu: `resources GECTI, fuzz KALDI, crash GECTI, bridge KALDI, network KALDI`. Network o koşuda panel ConnectionRefused verdi (yanlış port); bridge'de durum kirliliği vardı.

Düzeltme sonrası:
1. `python -B tests_hata\hepsi.py --only network` → `RESULT network GECTI` (py ve rs GECTI, gate_lan 0, panel 401/403/200 beklenen sırada)
2. `python -B tests_hata\hepsi.py --only bridge` → `RESULT bridge GECTI` (ayrıca bridge_rows.json: muaf dışı shape uyuşmazlığı 0)
3. Tam koşu `python -B tests_hata\hepsi.py` → EXIT=0:
   - `RESULT resources GECTI`
   - `RESULT fuzz GECTI`
   - `RESULT crash GECTI`
   - `RESULT bridge GECTI`
   - `RESULT network GECTI`
   - `CLEANUP all owned processes stopped: True`

Log dosyaları: `%TEMP%\...\scratchpad\full2.log`, `net2.log`, `bridge2.log`.

## Açık konu
- fuzz parite farkları (yukarıda) uygulama tarafında karar bekliyor; kod değişikliği için izin istenmeli.
