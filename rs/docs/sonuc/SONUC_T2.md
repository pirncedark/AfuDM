# T2 hata ve dayanıklılık sonuçları

Üretim kodundaki hatalar düzeltilmedi. Bu rapor gerçek test çıktılarını ve kapsam sınırlarını ayırır.

Rapor zamanı: 2026-10-18T07:01:36

## Durum

| Madde | Sonuç | Kanıt |
|---|---|---|
| 1 — POST fuzz | KALDI | [ham JSON](../../tests_hata/rapor/fuzz.json) |
| 2 — Çökme/yeniden başlatma | KALDI | [ham JSON](../../tests_hata/rapor/crash.json) |
| 3a — Kopya DB göçü | GEÇTİ | [ham JSON](../../tests_hata/rapor/migration.json) |
| 3b — Eski güncelleyici | GEÇTİ | [ham JSON](../../tests_hata/rapor/updater.json) |
| 4 — Köprü metotları | KALDI | [ham JSON](../../tests_hata/rapor/bridge.json) |
| 4 — Panel/LAN | GEÇTİ | [ham JSON](../../tests_hata/rapor/network.json) |
| 5 — RAM/CPU/disk | GEÇTİ | [ham JSON](../../tests_hata/rapor/resources.json) |

Süreç temizliği: `{"all_owned_processes_stopped": true, "remaining": []}`.

## Tekrarlama

```powershell
python -B tests_hata/verify.py
python -B tests_hata/hepsi.py
python -B tests_hata/upgrade.py
python -B tests_hata/report.py
```

Hepsi komutu 1, 2, 4 ve 5’i çalıştırır. Bir senaryo kaldığında çıkış kodu 1 olur; bu bir test bulgusudur.

## 1 — Hatalı girdiler

```json
{
  "status": "KALDI",
  "routes": [
    "/add",
    "/add_blob",
    "/control",
    "/eklenti",
    "/handoff/error",
    "/linkgrabber",
    "/mode",
    "/reliability/backup",
    "/reliability/diagnostics-export",
    "/reliability/diagnostics-preview",
    "/reliability/integrity",
    "/renew",
    "/rules",
    "/seed/tazele",
    "/settings",
    "/share_create",
    "/token/rotate",
    "/torrent/secim",
    "/tracker/tara",
    "/windows-integration"
  ],
  "cases": 300,
  "errors_500_or_disconnect": 1,
  "differences": 90,
  "masked_429": 0,
  "containment": [
    {
      "side": "py",
      "response": {
        "status": 403,
        "json": {
          "ok": false,
          "code": "HEDEF_DISARIDA",
          "message": "hedef klasor indirme kokunun disinda",
          "error": "hedef klasor indirme kokunun disinda"
        }
      },
      "outside_downloads_exists": false
    },
    {
      "side": "rs",
      "response": {
        "status": 403,
        "json": {
          "code": "HEDEF_DISARIDA",
          "error": "hedef klasor indirme kokunun disinda",
          "message": "hedef klasor indirme kokunun disinda",
          "ok": false
        }
      },
      "outside_downloads_exists": false
    }
  ],
  "limitations": [
    "No full-system write tracing; sentinel checks cover tested escape targets.",
    "Listener lifecycle POSTs can open windows or stop processes; excluded by explicit user safety requirement."
  ]
}
```

Bütün yanıt çiftleri: [fuzz_rows.json](../../tests_hata/rapor/fuzz_rows.json).


Planlanan vaka: 300; güvenlik nedeniyle atlanan: 6; her tarafta gönderilen: 294. Gerçek HTTP 500+: 0; taşıma hatası: 1.

| Yol | Farklı yanıt veren girdiler | 500/bağlantı hatası |
|---|---|---|
| /add | huge, unicode | huge |
| /add_blob | broken_json, list, null, bool, empty, wrong_types, unicode, traversal, file, javascript, wrong_origin |  |
| /control |  |  |
| /eklenti | broken_json, huge, list, null, bool |  |
| /handoff/error |  |  |
| /linkgrabber | broken_json, huge, list, null, bool |  |
| /mode |  |  |
| /reliability/backup | broken_json, huge, list, null, bool, empty, wrong_types, unicode, traversal, file, javascript, wrong_origin |  |
| /reliability/diagnostics-export | broken_json, huge, list, null, bool, empty, wrong_types, unicode, traversal, file, javascript, wrong_origin |  |
| /reliability/diagnostics-preview | broken_json, huge, list, null, bool, empty, wrong_types, unicode, traversal, file, javascript, wrong_origin |  |
| /reliability/integrity | broken_json, huge, list, null, bool, empty, wrong_types, unicode, traversal, file, javascript, wrong_origin |  |
| /renew |  |  |
| /rules | broken_json, huge, list, null, bool |  |
| /seed/tazele |  |  |
| /settings | empty, wrong_types, unicode, traversal, file, javascript, wrong_origin |  |
| /share_create | broken_json, huge |  |
| /token/rotate |  |  |
| /torrent/secim |  |  |
| /tracker/tara |  |  |
| /windows-integration | broken_json, huge, list, null, bool |  |

## 2 — Çökme ve devam

| Tür | Taraf | Sonuç | Çökme yüzdesi | .aria2 | Session bayt | DB | SHA | Range devam | taskkill kodu |
|---|---|---|---:|---|---:|---|---|---|---:|
| http | py | KALDI | 0.41162109375 | True | 0 | ok | False | False | 1 |
| http | rs | KALDI | 0.4043782552083333 | True | 0 | ok | False | False | 1 |

taskkill engellenirse yalnız sahip olunan süreç tanıtıcılarıyla zorla sonlandırma uygulanır. SHA-256 ve yeniden açıldıktan sonraki HTTP Range kayıtları ham JSON’dadır; yalnız dosya boyutu başarı sayılmaz.

## 3 — Güncelleme provası

```json
{
  "status": "GECTI",
  "copied": [
    "afudm.db",
    "afudm.db-wal",
    "afudm.db-shm"
  ],
  "before": {
    "integrity": "ok",
    "counts": {
      "downloads": 119,
      "settings": 73,
      "events": 10008,
      "automation_jobs": 76,
      "torrent_file_selections": 0,
      "mobile_devices": 0,
      "rules": 0,
      "plugins": 0,
      "api_keys": 1,
      "api_clients": 0,
      "server_profiles": 0
    },
    "settings_sha256": "1775700617f20866e1e0cd145b72f68057aa57b3666be2f083370869ab37a41f",
    "history_sha256": "e41ad55b7e3f072a7a993a0676e7d41cfd82c789de0471d1b48602efc6f34826",
    "user_version": 10
  },
  "after": {
    "integrity": "ok",
    "counts": {
      "downloads": 119,
      "settings": 73,
      "events": 10008,
      "automation_jobs": 76,
      "torrent_file_selections": 0,
      "mobile_devices": 0,
      "rules": 0,
      "plugins": 0,
      "api_keys": 1,
      "api_clients": 0,
      "server_profiles": 0
    },
    "settings_sha256": "1775700617f20866e1e0cd145b72f68057aa57b3666be2f083370869ab37a41f",
    "history_sha256": "e41ad55b7e3f072a7a993a0676e7d41cfd82c789de0471d1b48602efc6f34826",
    "user_version": 10
  },
  "exit_code": 0,
  "marker": true,
  "scope": "Real Rust SqliteStore open/migrations only; full Manager startup intentionally not used on copied user queue."
}
```

```json
{
  "status": "GECTI",
  "api": {
    "control": {
      "ok": true,
      "var": true,
      "mevcut": "2.9.8",
      "yeni": "3.0.0",
      "notlar": "T2 local update",
      "zip_url": "http://127.0.0.1:60599/AfuDM-v3.0.0-win64.zip",
      "sha_url": "http://127.0.0.1:60599/AfuDM-v3.0.0-win64.zip.sha256"
    },
    "download": {
      "ok": true,
      "yol": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_update_oq7p1zla\\upgrade\\data\\guncelleme\\yeni\\AfuDM"
    },
    "ready": true,
    "apply": {
      "ok": true,
      "kapat": true
    },
    "launcher_pids": [
      12100
    ]
  },
  "helper_exit": 0,
  "helper_stderr": "",
  "exe_replaced_sha256": "0771ab187c2609f8baa6d6c2af2b00edbf19457c671eb715842680fc34b04954",
  "extra_engine_preserved": true,
  "data_preserved": true,
  "relaunch_captured": true,
  "adaptations": [
    "SURUM=2.9.8 in isolated helper (available source reports 2.9.6)",
    "IZINLI_ONEK=loopback fake GitHub only",
    "Final PowerShell Start-Process intercepted to prevent any application/window launch; copy/backup script executed unchanged."
  ]
}
```

Kaynak sürümü 2.9.6’dır; 2.9.8 sürüm değeri yalnız izole helper içinde uygulanmıştır. Bu, özgün 2.9.8 kaynak sürümünün çalıştırıldığı anlamına gelmez. Gerçek DB bağlantısı açılmadan DB/WAL/SHM fiziksel olarak kopyalanır; SQLite yalnız kopyayı açar. Canlı dosyaların art arda kopyalanması atomik snapshot garantisi vermez. Göç testi SqliteStore göçünü çalıştırır; kullanıcı kuyruğunu başlatmaz. Güncelleyicide gerçek indirme, SHA kontrolü, zip açma, yedekleme ve kopyalama yolu çalışır; son EXE açılışı yakalanır.

### Release iş akışı önerisi — uygulanmadı

1. `.github/workflows/release.yml` içindeki quality-gate ve tag/main kontrollerini koru. `scripts/surum_oku.py` kontrolüne ek olarak `rs/app/Cargo.toml` ve Rust sürüm sabitinin tag ile eşitliğini denetle.
2. Windows job’a sabitlenmiş Rust araç zincirini ekle. PyInstaller adımı yerine `cargo build --release --locked --manifest-path rs/app/Cargo.toml` çalıştır; `test-kapisi` özelliğini açma.
3. Kök çalışma alanı ve ayrı app çalışma alanında fmt, test ve clippy kontrollerini çalıştır. Yayın öncesi bu T2 senaryolarındaki KALDI bulgularını çöz.
4. `rs/scripts/build_release_rust.ps1` önerilir (bu görevde scripts sahipliği yok; oluşturulmadı). Betik `rs/app/target/release/AfuDM.exe` dosyasını geçici `AfuDM/` köküne, gerekli motorları `AfuDM/engine/`, UI dosyalarını `AfuDM/ui/` içine koymalı. Kullanıcı data klasörünü pakete alma.
5. Kökü koruyarak `AfuDM-v3.0.0-win64.zip` oluştur. SHA-256 dosyası aynı isim + `.sha256` olsun. Önceki Python paketleme betiğinin PyInstaller çıktı yolunu Rust staging yoluna uyarla veya yeni betiğe yönlendir.
6. Mevcut verify_release/smoke_test betiklerini Rust paketine uyarlayıp izole veri/port ve penceresiz prova yaptır. Eski güncelleyicinin gerçek uygulama provası da kapı olmalı. Artifact/checksum/release notes/yayın adımlarını koru.

Üretilen prova zip’i geçici klasördeydi; kalıcı yayın paketi üretilmedi. Prova varsayılan DEBUG EXE’yi kullanır; optimize release paketi doğrulanmış sayılmaz.

## 4 — Köprü ve ağ

```json
{
  "status": "KALDI",
  "unique_public_methods": 146,
  "called": 115,
  "skipped": 31,
  "differences": 20
}
```

| Metot | Python sonuç biçimi | Rust sonuç biçimi |
|---|---|---|
| automation_cancel | {'status': 200, 'shape': {'ok': 'bool', 'job': 'null'}, 'ok': True, 'exception': None} | {'status': 200, 'shape': 'null', 'ok': None, 'exception': None} |
| automation_retry | {'status': 200, 'shape': {'ok': 'bool', 'job': 'null'}, 'ok': True, 'exception': None} | {'status': 200, 'shape': 'null', 'ok': None, 'exception': None} |
| bekleyen_iptal | {'status': 200, 'shape': {'ok': 'bool'}, 'ok': True, 'exception': None} | {'status': 200, 'shape': {'error': 'string', 'ok': 'bool'}, 'ok': False, 'exception': None} |
| butunluk_hepsini_tara | {'status': 200, 'shape': {'ok': 'bool', 'code': 'string', 'message': 'string', 'error': 'string'}, 'ok': False, 'exception': None} | {'status': 200, 'shape': {'ok': 'bool', 'sonuclar': {}, 'taranan': 'number'}, 'ok': True, 'exception': None} |
| control | {'status': 200, 'shape': {'ok': 'bool', 'code': 'string', 'error': 'string'}, 'ok': False, 'exception': None} | {'status': 200, 'shape': {'error': 'string', 'ok': 'bool'}, 'ok': False, 'exception': None} |
| link_yenile | {'status': 200, 'shape': {'ok': 'bool', 'code': 'string', 'message': 'string', 'error': 'string'}, 'ok': False, 'exception': None} | {'status': 200, 'shape': {'error': 'string', 'ok': 'bool'}, 'ok': False, 'exception': None} |
| motor_durumu | {'status': 200, 'shape': {'ok': 'bool', 'motorlar': {'aria2c': {'var': 'bool', 'kaynak': 'string', 'sistem_yolu': 'string', 'kullanilabilir': 'bool', 'boyut_mb': 'number', 'zorunlu': 'bool', 'ne_icin': 'string', 'indirme_boyutu_mb': 'number'}, 'yt-dlp': {'var': 'bool', 'kaynak': 'string', 'sistem_yolu': 'string', 'kullanilabilir': 'bool', 'boyut_mb': 'number', 'zorunlu': 'bool', 'ne_icin': 'string | {'status': 200, 'shape': {'ilerleme': {}, 'motorlar': {'aria2c': {'kaynak': 'string'}, 'cloudflared': {'kaynak': 'string'}, 'ffmpeg': {'kaynak': 'string'}, 'yt-dlp': {'kaynak': 'string'}}, 'ok': 'bool'}, 'ok': True, 'exception': None} |
| reliability_recovery_preview | {'status': 200, 'shape': {'__exception__': 'string', 'message': 'string'}, 'ok': None, 'exception': 'ValueError'} | {'status': 200, 'shape': {'error': 'string', 'ok': 'bool'}, 'ok': False, 'exception': None} |
| reliability_restore | {'status': 200, 'shape': {'__exception__': 'string', 'message': 'string'}, 'ok': None, 'exception': 'ValueError'} | {'status': 200, 'shape': {'error': 'string', 'ok': 'bool'}, 'ok': False, 'exception': None} |
| retry | {'status': 200, 'shape': {'ok': 'bool', 'code': 'string', 'message': 'string', 'error': 'string'}, 'ok': False, 'exception': None} | {'status': 200, 'shape': {'error': 'string', 'ok': 'bool'}, 'ok': False, 'exception': None} |
| sistem_durumu | {'status': 200, 'shape': {'ok': 'bool', 'baslangic': 'bool', 'torrent': {'torrent': {'kayitli': 'bool', 'varsayilan': 'bool'}, 'magnet': {'kayitli': 'bool', 'varsayilan': 'bool'}}}, 'ok': True, 'exception': None} | {'status': 200, 'shape': {'baslangic': 'bool', 'boot_hata': 'null', 'ok': 'bool', 'torrent': {'kayitli': 'bool', 'magnet': 'bool', 'torrent': 'bool'}}, 'ok': True, 'exception': None} |
| surum_bilgi | {'status': 200, 'shape': {'surum': 'string', 'uzanti': 'string'}, 'ok': None, 'exception': None} | {'status': 200, 'shape': {'ok': 'bool', 'surum': 'string', 'uzanti': 'null'}, 'ok': True, 'exception': None} |
| torrent_dosyalari | {'status': 200, 'shape': {'ok': 'bool', 'error_code': 'string', 'error': 'string', 'error_details': 'string'}, 'ok': False, 'exception': None} | {'status': 200, 'shape': {'error': 'string', 'ok': 'bool'}, 'ok': False, 'exception': None} |
| torrent_metrikleri | {'status': 200, 'shape': {'ok': 'bool', 'error_code': 'string', 'error': 'string', 'error_details': 'string', 'hazir_degil': 'bool', 'neden': 'string'}, 'ok': False, 'exception': None} | {'status': 200, 'shape': {'error': 'string', 'ok': 'bool'}, 'ok': False, 'exception': None} |
| torrent_on_ekle | {'status': 200, 'shape': {'ok': 'bool', 'error_code': 'string', 'error': 'string', 'error_details': 'string'}, 'ok': False, 'exception': None} | {'status': 200, 'shape': {'error': 'string', 'ok': 'bool'}, 'ok': False, 'exception': None} |
| torrent_secimi_ayarla | {'status': 200, 'shape': {'ok': 'bool', 'error_code': 'string', 'error': 'string', 'error_details': 'string'}, 'ok': False, 'exception': None} | {'status': 200, 'shape': {'error': 'string', 'ok': 'bool'}, 'ok': False, 'exception': None} |
| windows_integration_apply | {'status': 200, 'shape': {'__exception__': 'string', 'message': 'string'}, 'ok': None, 'exception': 'ValueError'} | {'status': 200, 'shape': {'error': 'string', 'ok': 'bool'}, 'ok': False, 'exception': None} |
| windows_integration_remove | {'status': 200, 'shape': {'__exception__': 'string', 'message': 'string'}, 'ok': None, 'exception': 'ValueError'} | {'status': 200, 'shape': {'error': 'string', 'ok': 'bool'}, 'ok': False, 'exception': None} |
| windows_integration_status | {'status': 200, 'shape': {'ok': 'bool', 'integrations': {'context': {'registered': 'bool', 'scope': 'string'}, 'protocol': {'registered': 'bool', 'scope': 'string'}, 'afup': {'registered': 'bool', 'scope': 'string'}, 'torrent': {'registered': 'bool', 'scope': 'string'}, 'startup': {'registered': 'bool', 'scope': 'string'}, 'notify': {'registered': 'bool', 'scope': 'string'}, 'defender': {'register | {'status': 200, 'shape': {'integrations': {'defender': {'available': 'bool', 'registered': 'bool', 'scope': 'string'}, 'notify': {'registered': 'bool', 'scope': 'string'}, 'protocol': {'registered': 'bool', 'scope': 'string'}, 'startup': {'registered': 'bool', 'scope': 'string'}, 'torrent': {'registered': 'bool', 'scope': 'string'}}, 'ok': 'bool'}, 'ok': True, 'exception': None} |
| windows_integration_test | {'status': 200, 'shape': {'__exception__': 'string', 'message': 'string'}, 'ok': None, 'exception': 'ValueError'} | {'status': 200, 'shape': {'error': 'string', 'ok': 'bool'}, 'ok': False, 'exception': None} |

Atlanan metotlar (başarı sayılmaz):

- `ana_pencere_kapandi`: window lifecycle
- `baslangic_ayarla`: user startup registry
- `chrome_ac`: browser window
- `chrome_hazirla`: may install browser using external Internet
- `chrome_kopyala`: user clipboard
- `chrome_otomatik`: browser/registry
- `dosya_sec_ve_paylas`: dialog
- `eklenti_klasoru_ac`: Explorer window
- `guncelleme_kontrol`: external GitHub request
- `klasor_gozat`: dialog
- `open_download_dir`: Explorer window
- `panodan_oku`: user clipboard
- `panoya_kopyala`: user clipboard
- `pencere_buyut`: window method
- `pencere_durumu`: window method
- `pencere_kapat`: window method
- `pencere_kenar`: window method
- `pencere_kucult`: window method
- `proxy_testi`: connectivity test can use external Internet
- `reliability_health`: test-only IdleRpc placeholder; production RPC ports forbidden
- `reliability_restart_engine`: Rust daemon scans production RPC port range
- `seed_dosya_ekle`: empty default opens file dialog
- `simdi_uyu`: would suspend user computer
- `sunucu_panel_ac`: browser window
- `tarayicidan_sor`: download dialog
- `torrent_iliskilendir`: user registry
- `tracker_klasoru_ac`: Explorer window
- `tracker_tara`: tracker scan can access external Internet
- `varsayilan_uygulama_ekrani`: opens settings window
- `windows`: window property, not callable

Kapı güvenlik yanıtları:

```json
[
  {
    "case": "missing_token",
    "status": 401,
    "expected": 401,
    "passed": true
  },
  {
    "case": "wrong_token",
    "status": 401,
    "expected": 401,
    "passed": true
  },
  {
    "case": "origin",
    "status": 401,
    "expected": 401,
    "passed": true
  },
  {
    "case": "broken_json",
    "status": 400,
    "expected": 400,
    "passed": true
  },
  {
    "case": "missing_fields",
    "status": 400,
    "expected": 400,
    "passed": true
  },
  {
    "case": "oversize",
    "status": 413,
    "expected": 413,
    "passed": true
  },
  {
    "case": "production_rpc_guard",
    "status": 403,
    "expected": 403,
    "passed": true
  }
]
```

Panel/LAN sonuçları:

```json
[
  {
    "side": "py",
    "settings": {
      "status": 200,
      "json": {
        "ok": true,
        "hatalar": [],
        "ayarlar": {
          "language": "auto",
          "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\py\\downloads",
          "max_concurrent": 5,
          "split": 64,
          "max_conn_per_server": 16,
          "max_speed_kb": 0,
          "hiz_profili": "normal",
          "snail_speed_kb": 100,
          "clipboard_watch": false,
          "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent",
          "notify_telegram": false,
          "windows_notifications": false,
          "telegram_bot_token": "[REDACTED]",
          "telegram_chat_id": "",
          "shutdown_when_done": false,
          "sleep_when_done": false,
          "seed_ratio": 1.0,
          "auto_update_trackers": false,
          "video_quality": "best",
          "api_listen_port": 6811,
          "api_port": 6811,
          "kaydetme_penceresi": false,
          "kategori_klasorleri": true,
          "tepsiye_kucult": true,
          "eklenti_max_boyut_mb": 200,
          "eklenti_max_oran": 100.0,
          "eklenti_imzasiz_izin": true,
          "baslangicta_tepside": true,
          "ek_trackerlar": "",
          "canli_trackerlar": "",
          "tracker_tarama_zamani": 0,
          "tracker_tarama_ozeti": {},
          "tracker_otomatik_tara": false,
          "lan_erisimi": false,
          "internet_paylasim": true,
          "ag_konumlari": "",
          "proxy": "",
          "system_proxy": false,
          "automation_enabled": false,
          "automation_steps": [
            "checksum",
            "extract",
            "move",
            "rename",
            "script",
            "notify",
            "power"
          ],
          "automation_checksum": true,
          "automation_extract": false,
          "automation_move_to": "",
          "automation_rename_to": "",
          "automation_script": "",
          "automation_notify": true,
          "automation_power": "none",
          "automation_power_seconds": 60,
          "sunucu_acik": false,
          "sunucu_adres": "lan",
          "sunucu_port": 56662,
          "sunucu_istek_limiti": 1000,
          "sunucu_hatali_limit": 8,
          "sunucu_kilit_saniye": 300,
          "sunucu_izinli_originler": "",
          "sunucu_istemci_kaydi": true,
          "sunucu_profil_id": 0,
          "sunucu_proxy_guven": false,
          "guncelleme_otomatik": false,
          "telefon_acik": false,
          "auto_accept_migrated": true
        },
        "settings": {
          "language": "auto",
          "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\py\\downloads",
          "max_concurrent": 5,
          "split": 64,
          "max_conn_per_server": 16,
          "max_speed_kb": 0,
          "hiz_profili": "normal",
          "snail_speed_kb": 100,
          "clipboard_watch": false,
          "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent",
          "notify_telegram": false,
          "windows_notifications": false,
          "telegram_bot_token": "[REDACTED]",
          "telegram_chat_id": "",
          "shutdown_when_done": false,
          "sleep_when_done": false,
          "seed_ratio": 1.0,
          "auto_update_trackers": false,
          "video_quality": "best",
          "api_listen_port": 6811,
          "api_port": 6811,
          "kaydetme_penceresi": false,
          "kategori_klasorleri": true,
          "tepsiye_kucult": true,
          "eklenti_max_boyut_mb": 200,
          "eklenti_max_oran": 100.0,
          "eklenti_imzasiz_izin": true,
          "baslangicta_tepside": true,
          "ek_trackerlar": "",
          "canli_trackerlar": "",
          "tracker_tarama_zamani": 0,
          "tracker_tarama_ozeti": {},
          "tracker_otomatik_tara": false,
          "lan_erisimi": false,
          "internet_paylasim": true,
          "ag_konumlari": "",
          "proxy": "",
          "system_proxy": false,
          "automation_enabled": false,
          "automation_steps": [
            "checksum",
            "extract",
            "move",
            "rename",
            "script",
            "notify",
            "power"
          ],
          "automation_checksum": true,
          "automation_extract": false,
          "automation_move_to": "",
          "automation_rename_to": "",
          "automation_script": "",
          "automation_notify": true,
          "automation_power": "none",
          "automation_power_seconds": 60,
          "sunucu_acik": false,
          "sunucu_adres": "lan",
          "sunucu_port": 56662,
          "sunucu_istek_limiti": 1000,
          "sunucu_hatali_limit": 8,
          "sunucu_kilit_saniye": 300,
          "sunucu_izinli_originler": "",
          "sunucu_istemci_kaydi": true,
          "sunucu_profil_id": 0,
          "sunucu_proxy_guven": false,
          "guncelleme_otomatik": false,
          "telefon_acik": false,
          "auto_accept_migrated": true
        }
      }
    },
    "opened": {
      "status": 200,
      "json": {
        "ok": true,
        "calisiyor": true,
        "istenen": true,
        "adres": "lan",
        "port": 56662,
        "url": "http://127.0.0.1:56662/panel",
        "lan_url": "http://192.168.0.110:56662/panel",
        "profil_id": 0,
        "profil_ad": "",
        "hata": "",
        "istek_sayisi": 0,
        "reddedilen": 0,
        "baslangic": 1792295758.224828
      }
    },
    "key_result_shape": {
      "ok": "bool",
      "id": "number",
      "ad": "string",
      "rol": "string",
      "gizli": "[REDACTED]",
      "olusturuldu": "number"
    },
    "panel": [
      {
        "host": "loopback",
        "case": "none",
        "result": {
          "status": 401,
          "json": {
            "ok": false,
            "code": "ANAHTAR_GEREKLI",
            "message": "erisim anahtari gerekli",
            "error": "erisim anahtari gerekli"
          }
        }
      },
      {
        "host": "loopback",
        "case": "invalid",
        "result": {
          "status": 401,
          "json": {
            "ok": false,
            "code": "GECERSIZ_ANAHTAR",
            "message": "anahtar gecersiz veya iptal edilmis",
            "error": "anahtar gecersiz veya iptal edilmis"
          }
        }
      },
      {
        "host": "loopback",
        "case": "valid",
        "result": {
          "status": 200,
          "json": {
            "items": [],
            "stat": {
              "downloadSpeed": 0,
              "uploadSpeed": 0,
              "numActive": 0,
              "numWaiting": 0,
              "numStopped": 0
            },
            "settings": {
              "language": "auto",
              "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\py\\downloads",
              "max_concurrent": 5,
              "split": 64,
              "max_conn_per_server": 16,
              "max_speed_kb": 0,
              "hiz_profili": "normal",
              "snail_speed_kb": 100,
              "clipboard_watch": false,
              "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent",
              "notify_telegram": false,
              "windows_notifications": false,
              "telegram_bot_token": "[REDACTED]",
              "telegram_chat_id": "",
              "shutdown_when_done": false,
              "sleep_when_done": false,
              "seed_ratio": 1.0,
              "auto_update_trackers": false,
              "video_quality": "best",
              "api_listen_port": 6811,
              "api_port": 6811,
              "kaydetme_penceresi": false,
              "kategori_klasorleri": true,
              "tepsiye_kucult": true,
              "eklenti_max_boyut_mb": 200,
              "eklenti_max_oran": 100.0,
              "eklenti_imzasiz_izin": true,
              "baslangicta_tepside": true,
              "ek_trackerlar": "",
              "canli_trackerlar": "",
              "tracker_tarama_zamani": 0,
              "tracker_tarama_ozeti": {},
              "tracker_otomatik_tara": false,
              "lan_erisimi": false,
              "internet_paylasim": true,
              "ag_konumlari": "",
              "proxy": "",
              "system_proxy": false,
              "automation_enabled": false,
              "automation_steps": [
                "checksum",
                "extract",
                "move",
                "rename",
                "script",
                "notify",
                "power"
              ],
              "automation_checksum": true,
              "automation_extract": false,
              "automation_move_to": "",
              "automation_rename_to": "",
              "automation_script": "",
              "automation_notify": true,
              "automation_power": "none",
              "automation_power_seconds": 60,
              "sunucu_acik": true,
              "sunucu_adres": "lan",
              "sunucu_port": 56662,
              "sunucu_istek_limiti": 1000,
              "sunucu_hatali_limit": 8,
              "sunucu_kilit_saniye": 300,
              "sunucu_izinli_originler": "",
              "sunucu_istemci_kaydi": true,
              "sunucu_profil_id": 0,
              "sunucu_proxy_guven": false,
              "guncelleme_otomatik": false,
              "telefon_acik": false,
              "auto_accept_migrated": true
            },
            "engine_ok": true,
            "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\py\\downloads",
            "lang": "tr",
            "last_error": "",
            "automation": [],
            "ok": true
          }
        }
      },
      {
        "host": "loopback",
        "case": "wrong_origin",
        "result": {
          "status": 403,
          "json": {
            "ok": false,
            "code": "ORIGIN_REDDEDILDI",
            "message": "bu adresten gelen istekler izinli degil",
            "error": "bu adresten gelen istekler izinli degil"
          }
        }
      },
      {
        "host": "LAN",
        "case": "none",
        "result": {
          "status": 401,
          "json": {
            "ok": false,
            "code": "ANAHTAR_GEREKLI",
            "message": "erisim anahtari gerekli",
            "error": "erisim anahtari gerekli"
          }
        }
      },
      {
        "host": "LAN",
        "case": "invalid",
        "result": {
          "status": 401,
          "json": {
            "ok": false,
            "code": "GECERSIZ_ANAHTAR",
            "message": "anahtar gecersiz veya iptal edilmis",
            "error": "anahtar gecersiz veya iptal edilmis"
          }
        }
      },
      {
        "host": "LAN",
        "case": "valid",
        "result": {
          "status": 200,
          "json": {
            "items": [],
            "stat": {
              "downloadSpeed": 0,
              "uploadSpeed": 0,
              "numActive": 0,
              "numWaiting": 0,
              "numStopped": 0
            },
            "settings": {
              "language": "auto",
              "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\py\\downloads",
              "max_concurrent": 5,
              "split": 64,
              "max_conn_per_server": 16,
              "max_speed_kb": 0,
              "hiz_profili": "normal",
              "snail_speed_kb": 100,
              "clipboard_watch": false,
              "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent",
              "notify_telegram": false,
              "windows_notifications": false,
              "telegram_bot_token": "[REDACTED]",
              "telegram_chat_id": "",
              "shutdown_when_done": false,
              "sleep_when_done": false,
              "seed_ratio": 1.0,
              "auto_update_trackers": false,
              "video_quality": "best",
              "api_listen_port": 6811,
              "api_port": 6811,
              "kaydetme_penceresi": false,
              "kategori_klasorleri": true,
              "tepsiye_kucult": true,
              "eklenti_max_boyut_mb": 200,
              "eklenti_max_oran": 100.0,
              "eklenti_imzasiz_izin": true,
              "baslangicta_tepside": true,
              "ek_trackerlar": "",
              "canli_trackerlar": "",
              "tracker_tarama_zamani": 0,
              "tracker_tarama_ozeti": {},
              "tracker_otomatik_tara": false,
              "lan_erisimi": false,
              "internet_paylasim": true,
              "ag_konumlari": "",
              "proxy": "",
              "system_proxy": false,
              "automation_enabled": false,
              "automation_steps": [
                "checksum",
                "extract",
                "move",
                "rename",
                "script",
                "notify",
                "power"
              ],
              "automation_checksum": true,
              "automation_extract": false,
              "automation_move_to": "",
              "automation_rename_to": "",
              "automation_script": "",
              "automation_notify": true,
              "automation_power": "none",
              "automation_power_seconds": 60,
              "sunucu_acik": true,
              "sunucu_adres": "lan",
              "sunucu_port": 56662,
              "sunucu_istek_limiti": 1000,
              "sunucu_hatali_limit": 8,
              "sunucu_kilit_saniye": 300,
              "sunucu_izinli_originler": "",
              "sunucu_istemci_kaydi": true,
              "sunucu_profil_id": 0,
              "sunucu_proxy_guven": false,
              "guncelleme_otomatik": false,
              "telefon_acik": false,
              "auto_accept_migrated": true
            },
            "engine_ok": true,
            "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\py\\downloads",
            "lang": "tr",
            "last_error": "",
            "automation": [],
            "ok": true
          }
        }
      },
      {
        "host": "LAN",
        "case": "wrong_origin",
        "result": {
          "status": 403,
          "json": {
            "ok": false,
            "code": "ORIGIN_REDDEDILDI",
            "message": "bu adresten gelen istekler izinli degil",
            "error": "bu adresten gelen istekler izinli degil"
          }
        }
      }
    ],
    "lan_opened_shape": {
      "ok": "bool",
      "acik": "bool",
      "adres": "string",
      "qr": "string",
      "port": "number"
    },
    "lan": [
      {
        "case": "none",
        "result": {
          "status": 401,
          "json": {
            "ok": false,
            "code": "GECERSIZ_TOKEN",
            "message": "gecersiz token",
            "error": "gecersiz token"
          }
        }
      },
      {
        "case": "invalid",
        "result": {
          "status": 401,
          "json": {
            "ok": false,
            "code": "GECERSIZ_TOKEN",
            "message": "gecersiz token",
            "error": "gecersiz token"
          }
        }
      },
      {
        "case": "valid",
        "result": {
          "status": 200,
          "json": {
            "ok": true,
            "items": [],
            "stat": {
              "downloadSpeed": 0,
              "uploadSpeed": 0,
              "numActive": 0,
              "numWaiting": 0,
              "numStopped": 0
            },
            "settings": {
              "language": "auto",
              "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\py\\downloads",
              "max_concurrent": 5,
              "split": 64,
              "max_conn_per_server": 16,
              "max_speed_kb": 0,
              "hiz_profili": "normal",
              "snail_speed_kb": 100,
              "clipboard_watch": false,
              "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent",
              "notify_telegram": false,
              "windows_notifications": false,
              "telegram_bot_token": "[REDACTED]",
              "telegram_chat_id": "",
              "shutdown_when_done": false,
              "sleep_when_done": false,
              "seed_ratio": 1.0,
              "auto_update_trackers": false,
              "video_quality": "best",
              "api_listen_port": 6811,
              "api_port": 56411,
              "kaydetme_penceresi": false,
              "kategori_klasorleri": true,
              "tepsiye_kucult": true,
              "eklenti_max_boyut_mb": 200,
              "eklenti_max_oran": 100.0,
              "eklenti_imzasiz_izin": true,
              "baslangicta_tepside": true,
              "ek_trackerlar": "",
              "canli_trackerlar": "",
              "tracker_tarama_zamani": 0,
              "tracker_tarama_ozeti": {},
              "tracker_otomatik_tara": false,
              "lan_erisimi": true,
              "internet_paylasim": true,
              "ag_konumlari": "",
              "proxy": "",
              "system_proxy": false,
              "automation_enabled": false,
              "automation_steps": [
                "checksum",
                "extract",
                "move",
                "rename",
                "script",
                "notify",
                "power"
              ],
              "automation_checksum": true,
              "automation_extract": false,
              "automation_move_to": "",
              "automation_rename_to": "",
              "automation_script": "",
              "automation_notify": true,
              "automation_power": "none",
              "automation_power_seconds": 60,
              "sunucu_acik": true,
              "sunucu_adres": "lan",
              "sunucu_port": 56662,
              "sunucu_istek_limiti": 1000,
              "sunucu_hatali_limit": 8,
              "sunucu_kilit_saniye": 300,
              "sunucu_izinli_originler": "",
              "sunucu_istemci_kaydi": true,
              "sunucu_profil_id": 0,
              "sunucu_proxy_guven": false,
              "guncelleme_otomatik": false,
              "telefon_acik": false,
              "auto_accept_migrated": true
            },
            "engine_ok": true,
            "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\py\\downloads",
            "lang": "tr",
            "last_error": "",
            "automation": []
          }
        }
      }
    ],
    "gate_lan_status": 0,
    "status": "GECTI"
  },
  {
    "side": "rs",
    "settings": {
      "status": 200,
      "json": {
        "ayarlar": {
          "ag_konumlari": "",
          "api_listen_port": 6811,
          "api_port": 6811,
          "auto_accept_migrated": true,
          "auto_update_trackers": false,
          "automation_checksum": true,
          "automation_enabled": false,
          "automation_extract": false,
          "automation_move_to": "",
          "automation_notify": true,
          "automation_power": "none",
          "automation_power_seconds": 60,
          "automation_rename_to": "",
          "automation_script": "",
          "automation_steps": [
            "checksum",
            "extract",
            "move",
            "rename",
            "script",
            "notify",
            "power"
          ],
          "baslangicta_tepside": true,
          "canli_trackerlar": "",
          "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent",
          "clipboard_watch": false,
          "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\rs\\downloads",
          "ek_trackerlar": "",
          "eklenti_imzasiz_izin": true,
          "eklenti_max_boyut_mb": 200,
          "eklenti_max_oran": 100.0,
          "guncelleme_otomatik": false,
          "hiz_profili": "normal",
          "internet_paylasim": true,
          "kategori_klasorleri": true,
          "kaydetme_penceresi": false,
          "lan_erisimi": false,
          "language": "auto",
          "max_concurrent": 5,
          "max_conn_per_server": 16,
          "max_speed_kb": 0,
          "notify_telegram": false,
          "proxy": "",
          "seed_ratio": 1.0,
          "shutdown_when_done": false,
          "sleep_when_done": false,
          "snail_speed_kb": 100,
          "split": 64,
          "sunucu_acik": false,
          "sunucu_adres": "lan",
          "sunucu_hatali_limit": 8,
          "sunucu_istek_limiti": 1000,
          "sunucu_istemci_kaydi": true,
          "sunucu_izinli_originler": "",
          "sunucu_kilit_saniye": 300,
          "sunucu_port": 56904,
          "sunucu_profil_id": 0,
          "sunucu_proxy_guven": false,
          "system_proxy": false,
          "telefon_acik": false,
          "telegram_bot_token": "[REDACTED]",
          "telegram_chat_id": "",
          "tepsiye_kucult": true,
          "tracker_otomatik_tara": false,
          "tracker_tarama_ozeti": {},
          "tracker_tarama_zamani": 0,
          "video_quality": "best",
          "windows_notifications": false
        },
        "hatalar": [],
        "ok": true,
        "settings": {
          "ag_konumlari": "",
          "api_listen_port": 6811,
          "api_port": 6811,
          "auto_accept_migrated": true,
          "auto_update_trackers": false,
          "automation_checksum": true,
          "automation_enabled": false,
          "automation_extract": false,
          "automation_move_to": "",
          "automation_notify": true,
          "automation_power": "none",
          "automation_power_seconds": 60,
          "automation_rename_to": "",
          "automation_script": "",
          "automation_steps": [
            "checksum",
            "extract",
            "move",
            "rename",
            "script",
            "notify",
            "power"
          ],
          "baslangicta_tepside": true,
          "canli_trackerlar": "",
          "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent",
          "clipboard_watch": false,
          "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\rs\\downloads",
          "ek_trackerlar": "",
          "eklenti_imzasiz_izin": true,
          "eklenti_max_boyut_mb": 200,
          "eklenti_max_oran": 100.0,
          "guncelleme_otomatik": false,
          "hiz_profili": "normal",
          "internet_paylasim": true,
          "kategori_klasorleri": true,
          "kaydetme_penceresi": false,
          "lan_erisimi": false,
          "language": "auto",
          "max_concurrent": 5,
          "max_conn_per_server": 16,
          "max_speed_kb": 0,
          "notify_telegram": false,
          "proxy": "",
          "seed_ratio": 1.0,
          "shutdown_when_done": false,
          "sleep_when_done": false,
          "snail_speed_kb": 100,
          "split": 64,
          "sunucu_acik": false,
          "sunucu_adres": "lan",
          "sunucu_hatali_limit": 8,
          "sunucu_istek_limiti": 1000,
          "sunucu_istemci_kaydi": true,
          "sunucu_izinli_originler": "",
          "sunucu_kilit_saniye": 300,
          "sunucu_port": 56904,
          "sunucu_profil_id": 0,
          "sunucu_proxy_guven": false,
          "system_proxy": false,
          "telefon_acik": false,
          "telegram_bot_token": "[REDACTED]",
          "telegram_chat_id": "",
          "tepsiye_kucult": true,
          "tracker_otomatik_tara": false,
          "tracker_tarama_ozeti": {},
          "tracker_tarama_zamani": 0,
          "video_quality": "best",
          "windows_notifications": false
        }
      }
    },
    "opened": {
      "status": 200,
      "json": {
        "adres": "lan",
        "baslangic": 1792295761.3445365,
        "calisiyor": true,
        "hata": "",
        "istek_sayisi": 0,
        "istenen": true,
        "lan_url": "http://192.168.0.110:56904/panel",
        "ok": true,
        "port": 56904,
        "profil_ad": "",
        "profil_id": 0,
        "reddedilen": 0,
        "url": "http://127.0.0.1:56904/panel"
      }
    },
    "key_result_shape": {
      "ad": "string",
      "gizli": "[REDACTED]",
      "id": "number",
      "ok": "bool",
      "olusturuldu": "number",
      "rol": "string"
    },
    "panel": [
      {
        "host": "loopback",
        "case": "none",
        "result": {
          "status": 401,
          "json": {
            "code": "ANAHTAR_GEREKLI",
            "error": "erisim anahtari gerekli",
            "message": "erisim anahtari gerekli",
            "ok": false
          }
        }
      },
      {
        "host": "loopback",
        "case": "invalid",
        "result": {
          "status": 401,
          "json": {
            "code": "GECERSIZ_ANAHTAR",
            "error": "anahtar gecersiz veya iptal edilmis",
            "message": "anahtar gecersiz veya iptal edilmis",
            "ok": false
          }
        }
      },
      {
        "host": "loopback",
        "case": "valid",
        "result": {
          "status": 200,
          "json": {
            "automation": [],
            "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\rs\\downloads",
            "engine_ok": true,
            "items": [],
            "lang": "tr",
            "last_error": "",
            "ok": true,
            "settings": {
              "ag_konumlari": "",
              "api_listen_port": 6811,
              "api_port": 6811,
              "auto_accept_migrated": true,
              "auto_update_trackers": false,
              "automation_checksum": true,
              "automation_enabled": false,
              "automation_extract": false,
              "automation_move_to": "",
              "automation_notify": true,
              "automation_power": "none",
              "automation_power_seconds": 60,
              "automation_rename_to": "",
              "automation_script": "",
              "automation_steps": [
                "checksum",
                "extract",
                "move",
                "rename",
                "script",
                "notify",
                "power"
              ],
              "baslangicta_tepside": true,
              "canli_trackerlar": "",
              "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent",
              "clipboard_watch": false,
              "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\rs\\downloads",
              "ek_trackerlar": "",
              "eklenti_imzasiz_izin": true,
              "eklenti_max_boyut_mb": 200,
              "eklenti_max_oran": 100.0,
              "guncelleme_otomatik": false,
              "hiz_profili": "normal",
              "internet_paylasim": true,
              "kategori_klasorleri": true,
              "kaydetme_penceresi": false,
              "lan_erisimi": false,
              "language": "auto",
              "max_concurrent": 5,
              "max_conn_per_server": 16,
              "max_speed_kb": 0,
              "notify_telegram": false,
              "proxy": "",
              "seed_ratio": 1.0,
              "shutdown_when_done": false,
              "sleep_when_done": false,
              "snail_speed_kb": 100,
              "split": 64,
              "sunucu_acik": true,
              "sunucu_adres": "lan",
              "sunucu_hatali_limit": 8,
              "sunucu_istek_limiti": 1000,
              "sunucu_istemci_kaydi": true,
              "sunucu_izinli_originler": "",
              "sunucu_kilit_saniye": 300,
              "sunucu_port": 56904,
              "sunucu_profil_id": 0,
              "sunucu_proxy_guven": false,
              "system_proxy": false,
              "telefon_acik": false,
              "telegram_bot_token": "[REDACTED]",
              "telegram_chat_id": "",
              "tepsiye_kucult": true,
              "tracker_otomatik_tara": false,
              "tracker_tarama_ozeti": {},
              "tracker_tarama_zamani": 0,
              "video_quality": "best",
              "windows_notifications": false
            },
            "stat": {
              "downloadSpeed": 0,
              "numActive": 0,
              "numStopped": 0,
              "numWaiting": 0,
              "uploadSpeed": 0
            }
          }
        }
      },
      {
        "host": "loopback",
        "case": "wrong_origin",
        "result": {
          "status": 403,
          "json": {
            "code": "ORIGIN_REDDEDILDI",
            "error": "bu adresten gelen istekler izinli degil",
            "message": "bu adresten gelen istekler izinli degil",
            "ok": false
          }
        }
      },
      {
        "host": "LAN",
        "case": "none",
        "result": {
          "status": 401,
          "json": {
            "code": "ANAHTAR_GEREKLI",
            "error": "erisim anahtari gerekli",
            "message": "erisim anahtari gerekli",
            "ok": false
          }
        }
      },
      {
        "host": "LAN",
        "case": "invalid",
        "result": {
          "status": 401,
          "json": {
            "code": "GECERSIZ_ANAHTAR",
            "error": "anahtar gecersiz veya iptal edilmis",
            "message": "anahtar gecersiz veya iptal edilmis",
            "ok": false
          }
        }
      },
      {
        "host": "LAN",
        "case": "valid",
        "result": {
          "status": 200,
          "json": {
            "automation": [],
            "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\rs\\downloads",
            "engine_ok": true,
            "items": [],
            "lang": "tr",
            "last_error": "",
            "ok": true,
            "settings": {
              "ag_konumlari": "",
              "api_listen_port": 6811,
              "api_port": 6811,
              "auto_accept_migrated": true,
              "auto_update_trackers": false,
              "automation_checksum": true,
              "automation_enabled": false,
              "automation_extract": false,
              "automation_move_to": "",
              "automation_notify": true,
              "automation_power": "none",
              "automation_power_seconds": 60,
              "automation_rename_to": "",
              "automation_script": "",
              "automation_steps": [
                "checksum",
                "extract",
                "move",
                "rename",
                "script",
                "notify",
                "power"
              ],
              "baslangicta_tepside": true,
              "canli_trackerlar": "",
              "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent",
              "clipboard_watch": false,
              "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\rs\\downloads",
              "ek_trackerlar": "",
              "eklenti_imzasiz_izin": true,
              "eklenti_max_boyut_mb": 200,
              "eklenti_max_oran": 100.0,
              "guncelleme_otomatik": false,
              "hiz_profili": "normal",
              "internet_paylasim": true,
              "kategori_klasorleri": true,
              "kaydetme_penceresi": false,
              "lan_erisimi": false,
              "language": "auto",
              "max_concurrent": 5,
              "max_conn_per_server": 16,
              "max_speed_kb": 0,
              "notify_telegram": false,
              "proxy": "",
              "seed_ratio": 1.0,
              "shutdown_when_done": false,
              "sleep_when_done": false,
              "snail_speed_kb": 100,
              "split": 64,
              "sunucu_acik": true,
              "sunucu_adres": "lan",
              "sunucu_hatali_limit": 8,
              "sunucu_istek_limiti": 1000,
              "sunucu_istemci_kaydi": true,
              "sunucu_izinli_originler": "",
              "sunucu_kilit_saniye": 300,
              "sunucu_port": 56904,
              "sunucu_profil_id": 0,
              "sunucu_proxy_guven": false,
              "system_proxy": false,
              "telefon_acik": false,
              "telegram_bot_token": "[REDACTED]",
              "telegram_chat_id": "",
              "tepsiye_kucult": true,
              "tracker_otomatik_tara": false,
              "tracker_tarama_ozeti": {},
              "tracker_tarama_zamani": 0,
              "video_quality": "best",
              "windows_notifications": false
            },
            "stat": {
              "downloadSpeed": 0,
              "numActive": 0,
              "numStopped": 0,
              "numWaiting": 0,
              "uploadSpeed": 0
            }
          }
        }
      },
      {
        "host": "LAN",
        "case": "wrong_origin",
        "result": {
          "status": 403,
          "json": {
            "code": "ORIGIN_REDDEDILDI",
            "error": "bu adresten gelen istekler izinli degil",
            "message": "bu adresten gelen istekler izinli degil",
            "ok": false
          }
        }
      }
    ],
    "lan_opened_shape": {
      "acik": "bool",
      "adres": "string",
      "ok": "bool",
      "port": "number",
      "qr": "string"
    },
    "lan": [
      {
        "case": "none",
        "result": {
          "status": 401,
          "json": {
            "code": "GECERSIZ_TOKEN",
            "error": "gecersiz token",
            "message": "gecersiz token",
            "ok": false
          }
        }
      },
      {
        "case": "invalid",
        "result": {
          "status": 401,
          "json": {
            "code": "GECERSIZ_TOKEN",
            "error": "gecersiz token",
            "message": "gecersiz token",
            "ok": false
          }
        }
      },
      {
        "case": "valid",
        "result": {
          "status": 200,
          "json": {
            "automation": [],
            "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\rs\\downloads",
            "engine_ok": true,
            "items": [],
            "lang": "tr",
            "last_error": "",
            "ok": true,
            "settings": {
              "ag_konumlari": "",
              "api_listen_port": 6811,
              "api_port": 56557,
              "auto_accept_migrated": true,
              "auto_update_trackers": false,
              "automation_checksum": true,
              "automation_enabled": false,
              "automation_extract": false,
              "automation_move_to": "",
              "automation_notify": true,
              "automation_power": "none",
              "automation_power_seconds": 60,
              "automation_rename_to": "",
              "automation_script": "",
              "automation_steps": [
                "checksum",
                "extract",
                "move",
                "rename",
                "script",
                "notify",
                "power"
              ],
              "baslangicta_tepside": true,
              "canli_trackerlar": "",
              "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent",
              "clipboard_watch": false,
              "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_g4s7bn3p\\rs\\downloads",
              "ek_trackerlar": "",
              "eklenti_imzasiz_izin": true,
              "eklenti_max_boyut_mb": 200,
              "eklenti_max_oran": 100.0,
              "guncelleme_otomatik": false,
              "hiz_profili": "normal",
              "internet_paylasim": true,
              "kategori_klasorleri": true,
              "kaydetme_penceresi": false,
              "lan_erisimi": true,
              "language": "auto",
              "max_concurrent": 5,
              "max_conn_per_server": 16,
              "max_speed_kb": 0,
              "notify_telegram": false,
              "proxy": "",
              "seed_ratio": 1.0,
              "shutdown_when_done": false,
              "sleep_when_done": false,
              "snail_speed_kb": 100,
              "split": 64,
              "sunucu_acik": true,
              "sunucu_adres": "lan",
              "sunucu_hatali_limit": 8,
              "sunucu_istek_limiti": 1000,
              "sunucu_istemci_kaydi": true,
              "sunucu_izinli_originler": "",
              "sunucu_kilit_saniye": 300,
              "sunucu_port": 56904,
              "sunucu_profil_id": 0,
              "sunucu_proxy_guven": false,
              "system_proxy": false,
              "telefon_acik": false,
              "telegram_bot_token": "[REDACTED]",
              "telegram_chat_id": "",
              "tepsiye_kucult": true,
              "tracker_otomatik_tara": false,
              "tracker_tarama_ozeti": {},
              "tracker_tarama_zamani": 0,
              "video_quality": "best",
              "windows_notifications": false
            },
            "stat": {
              "downloadSpeed": 0,
              "numActive": 0,
              "numStopped": 0,
              "numWaiting": 0,
              "uploadSpeed": 0
            }
          }
        }
      }
    ],
    "gate_lan_status": 0,
    "status": "GECTI"
  }
]
```

Panel normalde 6821 kullanır; bu testte mevcut kurulumla çakışmayı önlemek için geçici port seçilir. Test kapısı yalnız 127.0.0.1’e bağlanır; token ister ve Origin başlığını reddeder.

## 5 — Ölçümler

| Senaryo | Taraf | Örnek | WS MiB ort. | Private MiB ort. | CPU % ort. | Yazma MiB/s ort. | En çok süreç |
|---|---|---:|---:|---:|---:|---:|---:|
| idle | py | 149 | 44.839 | 24.483 | 0.166 | 0.000 | 4 |
| idle | rs | 149 | 71.527 | 11.940 | 1.122 | 0.000 | 4 |
| 1GiB | py | 30 | 57.551 | 29.987 | 5.694 | 16.815 | 4 |
| 1GiB | rs | 30 | 74.803 | 14.326 | 6.071 | 16.822 | 4 |
| 3_concurrent | py | 30 | 55.368 | 27.944 | 2.898 | 6.064 | 4 |
| 3_concurrent | rs | 30 | 74.657 | 14.483 | 4.089 | 6.253 | 4 |

Working Set/Private Bytes ve CPU/disk sayaçları bütün mevcut alt süreçler dahil psutil ile toplanır. CPU % tek mantıksal çekirdek ölçeğindedir (çok çekirdekte 100’ü geçebilir). İndirme pencereleri 60 saniyedir; indirme erken biterse kalan boş süre de ortalamaya girer. Her taraf 1 GiB HTTP ve üç eşzamanlı 128 MiB dosya indirir. İçerik SHA-256 ile denetlenir. Rust DEBUG derlemesidir. Test boot üretim IdleRpc uyku döngüsünü çalıştırmadığı için bu veriler nihai üretim performansı veya uyku davranışı karşılaştırması değildir.

## Yazılan dosyalar ve sözleşme sınırları

- `app/Cargo.toml`: varsayılan kapalı `test-kapisi` özelliği.
- `app/src/main.rs`: özellik kapıları; varsayılan boot/tray/single-instance yolu korunur.
- `app/src/test_kapisi.rs`: token korumalı köprü, izole boot, kopya DB göç modu ve güvenlik birim testi.
- `tests_hata/`: Python headless helper, ortak izolasyon, beş senaryo, güncelleme provası, doğrulama, rapor betiği, README ve ham çıktılar.
- `docs/sonuc/SONUC_T2.md`: bu rapor.

Python iş mantığı taşınmadı; mevcut Python Api ve Rust bridge::api_call/dispatch gerçek uygulamaları çağrıldı. ✅ Token/Origin/uzak adres birim testi ve her çağrının biçim kaydı. ⚠ Pencere, işletim sistemi değişikliği ve dış internet gerektiren metotlar yukarıda gerekçeleriyle atlandı. ⚠ Üretim Aria2Daemon 6810..6830 aralığını tarar; bu testte çalıştırılmaz. Üretim argümanları include edilip Manager’a ayrı RPC enjekte edilir. reliability_health/reliability_restart_engine bu nedenle atlanır. Sentinel kontrolleri bütün sistem yazma izlemesi değildir. Üretim uyku/restart ve tüm 146 metot kapsamı tamamlandı sayılmaz.

Uygulama hata düzeltmesi: yok. Önceki turdan kalan test kodundaki migration EXE yolu `tests_hata/bin/AfuDM_test.exe` olarak düzeltildi; varsayılan EXE’de göç modu derlenmez. Runner sonraki koşularda eski sonuçları başarı saymamak için seçili senaryo özetlerini temizler.

Son turda yalnız test betikleri düzeltildi: çökme ilerlemesi DB alanı `done_bytes` yerine snapshot alanı `completedLength` üzerinden okunur; panel yetkilendirme testi mevcut `/api/liste` yolunu kullanır. API envanterindeki `windows` özelliği açıkça atlanarak 146 benzersiz adın tamamı kayda alınır. 115 çağrı ve 31 atlama vardır. Hatalı ilerleme alanıyla başlatılan ilk prova yalnız kendi süreç ağacı kapatılarak durduruldu; sonuç olarak kullanılmadı. Kaynak ölçümü ve göç/güncelleme kanıtları önceki turdan korundu; eksik senaryolar `--only` ile ayrı izole çalıştırmalarda tamamlandı. Üretilen EXE `tests_hata/bin/` altında yereldir ve git dışında tutulur.

## Derleme / test / clippy gerçek çıktıları

### build_feature

`cargo build --manifest-path app/Cargo.toml --features test-kapisi --offline`

Çıkış: `0`, binary test kapısı işareti: `True`

```text
   Compiling afudm-app v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 8.20s
```

### test_feature

`cargo test --manifest-path app/Cargo.toml --features test-kapisi --offline`

Çıkış: `0`

```text
     Running unittests src\main.rs (app\target\debug\deps\AfuDM-9e76e09500124180.exe)

running 24 tests
test kopru_g::tests::defender_durum_varsayilani_idle ... ok
test kopru_g::tests::indirme_istegi_http_ad_ve_bayraklar ... ok
test kopru_g::tests::indirme_istegi_torrent_ve_zamanlama ... ok
test kopru_g::tests::linkgrabber_suz_boyut_aralik_bozuksa_yok_sayar ... ok
test kopru_g::tests::toplu_liste_urls_ve_tek_url_ile_calisir ... ok
test kopru_g::tests::kural_simule_eslesme_ve_catisma_yok ... ok
test kopru_g::tests::kural_temizle_python_kurallari ... ok
test kopru_g::tests::probe_ogeleri_eksik_sonuc_varsayilani ... ok
test kopru_g::tests::sayi_al_python_int_gibi ... ok
test kopru_g::tests::proxy_testi_bos_ve_uzun_girdi ... ok
test kopru_g::tests::proxy_bicim_denetimi ... ok
test kopru_g::tests::uuid_biçimi_ve_surumu ... ok
test kopru_g::tests::uygulama_zamani_tablosu ... ok
test kopru_h::tests::gecersiz_girdi_bad_request_doner ... ok
test kopru_h::tests::kart_satiri_ayristirilir_ve_mac_buyuk_harf ... ok
test kopru_h::tests::ok_birlestir_alanlari_ekler ... ok
test kopru_h::tests::uyandirma_metni_ag_kartini_tanir ... ok
test kopru_h::tests::wol_metni_true_false_veya_bilinmez ... ok
test test_kapisi::tests::token_origin_and_remote_clients_are_rejected ... ok
test yonetim::tests::filtre_ve_arama ... ok
test yonetim::tests::sorgu_cozulur ... ok
test yonetim::tests::yol_sondaki_bolu_kesilir ... ok
test kopru_g::tests::linkgrabber_analiz_ve_filtre ... ok
test yonetim::tests::qr_png_data_uri_olusur ... ok

test result: ok. 24 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.02s

```

### clippy_feature

`cargo clippy --manifest-path app/Cargo.toml --features test-kapisi --offline -- -D warnings`

Çıkış: `0`

```text
   Compiling afudm-app v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 1.81s
```

### build_default

`cargo build --manifest-path app/Cargo.toml --offline`

Çıkış: `0`, binary test kapısı işareti: `False`

```text
   Compiling afudm-app v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 7.43s
```

### test_default

`cargo test --manifest-path app/Cargo.toml --offline`

Çıkış: `0`

```text
    Finished `test` profile [unoptimized + debuginfo] target(s) in 6.72s
     Running unittests src\main.rs (app\target\debug\deps\AfuDM-d5d51ce2d7eb3395.exe)

running 23 tests
test kopru_g::tests::defender_durum_varsayilani_idle ... ok
test kopru_g::tests::indirme_istegi_http_ad_ve_bayraklar ... ok
test kopru_g::tests::indirme_istegi_torrent_ve_zamanlama ... ok
test kopru_g::tests::kural_temizle_python_kurallari ... ok
test kopru_g::tests::kural_simule_eslesme_ve_catisma_yok ... ok
test kopru_g::tests::linkgrabber_suz_boyut_aralik_bozuksa_yok_sayar ... ok
test kopru_g::tests::probe_ogeleri_eksik_sonuc_varsayilani ... ok
test kopru_g::tests::proxy_bicim_denetimi ... ok
test kopru_g::tests::proxy_testi_bos_ve_uzun_girdi ... ok
test kopru_g::tests::sayi_al_python_int_gibi ... ok
test kopru_g::tests::toplu_liste_urls_ve_tek_url_ile_calisir ... ok
test kopru_g::tests::uuid_biçimi_ve_surumu ... ok
test kopru_g::tests::uygulama_zamani_tablosu ... ok
test kopru_h::tests::gecersiz_girdi_bad_request_doner ... ok
test kopru_h::tests::kart_satiri_ayristirilir_ve_mac_buyuk_harf ... ok
test kopru_h::tests::ok_birlestir_alanlari_ekler ... ok
test kopru_h::tests::uyandirma_metni_ag_kartini_tanir ... ok
test kopru_h::tests::wol_metni_true_false_veya_bilinmez ... ok
test yonetim::tests::filtre_ve_arama ... ok
test yonetim::tests::sorgu_cozulur ... ok
test yonetim::tests::yol_sondaki_bolu_kesilir ... ok
test kopru_g::tests::linkgrabber_analiz_ve_filtre ... ok
test yonetim::tests::qr_png_data_uri_olusur ... ok

test result: ok. 23 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.02s

```

### clippy_default

`cargo clippy --manifest-path app/Cargo.toml --offline -- -D warnings`

Çıkış: `0`

```text
   Compiling afudm-app v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 1.79s
```

### format_owned

`rustfmt --edition 2021 --check --config skip_children=true app/src/main.rs app/src/test_kapisi.rs`

Çıkış: `0`

```text

```

## 📍 Yeniden üretilebilir bulgular

### 📍 automation_cancel — app/src/bridge.rs:841

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "automation_cancel", "args": [0]}`.

Python referansı: `P/app.py:1153`. Beklenen Python biçimi: `{"ok": "bool", "job": "null"}`. Gerçek Rust biçimi: `"null"`.

### 📍 automation_retry — app/src/bridge.rs:840

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "automation_retry", "args": [0]}`.

Python referansı: `P/app.py:1149`. Beklenen Python biçimi: `{"ok": "bool", "job": "null"}`. Gerçek Rust biçimi: `"null"`.

### 📍 bekleyen_iptal — app/src/bridge.rs:656

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "bekleyen_iptal", "args": [0]}`.

Python referansı: `P/app.py:680`. Beklenen Python biçimi: `{"ok": "bool"}`. Gerçek Rust biçimi: `{"error": "string", "ok": "bool"}`.

### 📍 butunluk_hepsini_tara — app/src/kopru_h.rs:106

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "butunluk_hepsini_tara", "args": []}`.

Python referansı: `P/app.py:1127`. Beklenen Python biçimi: `{"ok": "bool", "code": "string", "message": "string", "error": "string"}`. Gerçek Rust biçimi: `{"ok": "bool", "sonuclar": {}, "taranan": "number"}`.

### 📍 control — app/src/bridge.rs:888

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "control", "args": ["invalid-t2", "invalid-t2", false]}`.

Python referansı: `P/app.py:1111`. Beklenen Python biçimi: `{"ok": "bool", "code": "string", "error": "string"}`. Gerçek Rust biçimi: `{"error": "string", "ok": "bool"}`.

### 📍 link_yenile — app/src/bridge.rs:913

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "link_yenile", "args": ["invalid-t2", "http://127.0.0.1:58894/missing"]}`.

Python referansı: `P/app.py:1118`. Beklenen Python biçimi: `{"ok": "bool", "code": "string", "message": "string", "error": "string"}`. Gerçek Rust biçimi: `{"error": "string", "ok": "bool"}`.

### 📍 motor_durumu — app/src/bridge.rs:667

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "motor_durumu", "args": []}`.

Python referansı: `P/app.py:284`. Beklenen Python biçimi: `{"ok": "bool", "motorlar": {"aria2c": {"var": "bool", "kaynak": "string", "sistem_yolu": "string", "kullanilabilir": "bool", "boyut_mb": "number", "zorunlu": "bool", "ne_icin": "string", "indirme_boyutu_mb": "number"}, "yt-dlp": {"var": "bool", "kaynak": "string", "sistem_yolu": "string", "kullanilabilir": "bool", "boyut_mb": "number", "zorunlu": "bool", "ne_icin": "string", "indirme_boyutu_mb": "number"}, "ffmpeg": {"var": "bool", "kaynak": "string", "sistem_yolu": "string", "kullanilabilir": "bool", "boyut_mb": "number", "zorunlu": "bool", "ne_icin": "string", "indirme_boyutu_mb": "number"}, "cloudflared": {"var": "bool", "kaynak": "string", "sistem_yolu": "string", "kullanilabilir": "bool", "boyut_mb": "number", "zorunlu": "bool", "ne_icin": "string", "indirme_boyutu_mb": "number"}}, "ilerleme": {}}`. Gerçek Rust biçimi: `{"ilerleme": {}, "motorlar": {"aria2c": {"kaynak": "string"}, "cloudflared": {"kaynak": "string"}, "ffmpeg": {"kaynak": "string"}, "yt-dlp": {"kaynak": "string"}}, "ok": "bool"}`.

### 📍 reliability_recovery_preview — app/src/kopru_h.rs:109

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "reliability_recovery_preview", "args": [0]}`.

Python referansı: `P/app.py:254`. Beklenen Python biçimi: `{"__exception__": "string", "message": "string"}`. Gerçek Rust biçimi: `{"error": "string", "ok": "bool"}`.

Python geçersiz girdide `ValueError` yükseltiyor; helper bunu yakalar. Bu satır Rust çökmesi veya geçerli girdi başarısızlığı anlamına gelmez.

### 📍 reliability_restore — app/src/bridge.rs:800

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "reliability_restore", "args": ["__T2_BASE__/missing"]}`.

Python referansı: `P/app.py:249`. Beklenen Python biçimi: `{"__exception__": "string", "message": "string"}`. Gerçek Rust biçimi: `{"error": "string", "ok": "bool"}`.

Python geçersiz girdide `ValueError` yükseltiyor; helper bunu yakalar. Bu satır Rust çökmesi veya geçerli girdi başarısızlığı anlamına gelmez.

### 📍 retry — app/src/bridge.rs:897

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "retry", "args": [0]}`.

Python referansı: `P/app.py:1115`. Beklenen Python biçimi: `{"ok": "bool", "code": "string", "message": "string", "error": "string"}`. Gerçek Rust biçimi: `{"error": "string", "ok": "bool"}`.

### 📍 sistem_durumu — app/src/bridge.rs:668

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "sistem_durumu", "args": []}`.

Python referansı: `P/app.py:760`. Beklenen Python biçimi: `{"ok": "bool", "baslangic": "bool", "torrent": {"torrent": {"kayitli": "bool", "varsayilan": "bool"}, "magnet": {"kayitli": "bool", "varsayilan": "bool"}}}`. Gerçek Rust biçimi: `{"baslangic": "bool", "boot_hata": "null", "ok": "bool", "torrent": {"kayitli": "bool", "magnet": "bool", "torrent": "bool"}}`.

### 📍 surum_bilgi — app/src/bridge.rs:666

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "surum_bilgi", "args": []}`.

Python referansı: `P/app.py:322`. Beklenen Python biçimi: `{"surum": "string", "uzanti": "string"}`. Gerçek Rust biçimi: `{"ok": "bool", "surum": "string", "uzanti": "null"}`.

### 📍 torrent_dosyalari — app/src/bridge.rs:862

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "torrent_dosyalari", "args": ["invalid-t2"]}`.

Python referansı: `P/app.py:899`. Beklenen Python biçimi: `{"ok": "bool", "error_code": "string", "error": "string", "error_details": "string"}`. Gerçek Rust biçimi: `{"error": "string", "ok": "bool"}`.

### 📍 torrent_metrikleri — app/src/bridge.rs:875

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "torrent_metrikleri", "args": ["invalid-t2"]}`.

Python referansı: `P/app.py:921`. Beklenen Python biçimi: `{"ok": "bool", "error_code": "string", "error": "string", "error_details": "string", "hazir_degil": "bool", "neden": "string"}`. Gerçek Rust biçimi: `{"error": "string", "ok": "bool"}`.

### 📍 torrent_on_ekle — app/src/bridge.rs:856

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "torrent_on_ekle", "args": ["invalid-t2"]}`.

Python referansı: `P/app.py:883`. Beklenen Python biçimi: `{"ok": "bool", "error_code": "string", "error": "string", "error_details": "string"}`. Gerçek Rust biçimi: `{"error": "string", "ok": "bool"}`.

### 📍 torrent_secimi_ayarla — app/src/bridge.rs:874

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "torrent_secimi_ayarla", "args": ["invalid-t2", []]}`.

Python referansı: `P/app.py:915`. Beklenen Python biçimi: `{"ok": "bool", "error_code": "string", "error": "string", "error_details": "string"}`. Gerçek Rust biçimi: `{"error": "string", "ok": "bool"}`.

### 📍 windows_integration_apply — app/src/bridge.rs:706

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "windows_integration_apply", "args": ["invalid-t2"]}`.

Python referansı: `P/app.py:817`. Beklenen Python biçimi: `{"__exception__": "string", "message": "string"}`. Gerçek Rust biçimi: `{"error": "string", "ok": "bool"}`.

Python geçersiz girdide `ValueError` yükseltiyor; helper bunu yakalar. Bu satır Rust çökmesi veya geçerli girdi başarısızlığı anlamına gelmez.

### 📍 windows_integration_remove — app/src/bridge.rs:707

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "windows_integration_remove", "args": ["invalid-t2"]}`.

Python referansı: `P/app.py:836`. Beklenen Python biçimi: `{"__exception__": "string", "message": "string"}`. Gerçek Rust biçimi: `{"error": "string", "ok": "bool"}`.

Python geçersiz girdide `ValueError` yükseltiyor; helper bunu yakalar. Bu satır Rust çökmesi veya geçerli girdi başarısızlığı anlamına gelmez.

### 📍 windows_integration_status — app/src/bridge.rs:705

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "windows_integration_status", "args": []}`.

Python referansı: `P/app.py:801`. Beklenen Python biçimi: `{"ok": "bool", "integrations": {"context": {"registered": "bool", "scope": "string"}, "protocol": {"registered": "bool", "scope": "string"}, "afup": {"registered": "bool", "scope": "string"}, "torrent": {"registered": "bool", "scope": "string"}, "startup": {"registered": "bool", "scope": "string"}, "notify": {"registered": "bool", "scope": "string"}, "defender": {"registered": "bool", "scope": "string", "available": "bool"}}, "scan": {"state": "string", "path": "string", "detail": "string"}, "service": {"supported": "bool", "state": "string", "reason": "string"}}`. Gerçek Rust biçimi: `{"integrations": {"defender": {"available": "bool", "registered": "bool", "scope": "string"}, "notify": {"registered": "bool", "scope": "string"}, "protocol": {"registered": "bool", "scope": "string"}, "startup": {"registered": "bool", "scope": "string"}, "torrent": {"registered": "bool", "scope": "string"}}, "ok": "bool"}`.

### 📍 windows_integration_test — app/src/bridge.rs:708

Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `{"name": "windows_integration_test", "args": ["invalid-t2"]}`.

Python referansı: `P/app.py:853`. Beklenen Python biçimi: `{"__exception__": "string", "message": "string"}`. Gerçek Rust biçimi: `{"error": "string", "ok": "bool"}`.

Python geçersiz girdide `ValueError` yükseltiyor; helper bunu yakalar. Bu satır Rust çökmesi veya geçerli girdi başarısızlığı anlamına gelmez.

### 📍 POST yanıt uyumsuzlukları

Yeniden üret: `python -B tests_hata/hepsi.py --only fuzz`. Girdiler `tests_hata/scenarios.py` içindeki `cases` listesinde; tüm gerçek yanıtlar `tests_hata/rapor/fuzz_rows.json` içinde.

| Konum | Girdi | Beklenen Python | Gerçek Rust |
|---|---|---|---|
| `crates/afudm-api/src/lib.rs:42` | `/add` / huge | {"status": 0, "exception": "ConnectionAbortedError"} | {"status": 413, "json": {"code": "GOVDE_HATASI", "error": "Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "message": "Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "ok": false}} |
| `crates/afudm-api/src/lib.rs:42` | `/add` / unicode | {"status": 200, "json": {"ok": true, "id": 1, "gid": "aa7bd39129066188", "kind": "http"}} | {"status": 200, "json": {"gid": "bd60694ebaeaed63", "id": 1, "kind": "http", "ok": true}} |
| `crates/afudm-api/src/lib.rs:41` | `/add_blob` / broken_json | {"status": 200, "json": {"ok": true, "id": 2, "gid": "local:146679bb496b4ab5b9e0a24f040f6251", "kind": "http"}} | {"status": 200, "json": {"gid": "local:55b15a56d0994a11943a45311a65a773", "id": 2, "kind": "http", "ok": true}} |
| `crates/afudm-api/src/lib.rs:41` | `/add_blob` / list | {"status": 200, "json": {"ok": true, "id": 3, "gid": "local:0c80d938e73c44b0ad2f9a8855fa252b", "kind": "http"}} | {"status": 200, "json": {"gid": "local:49a54ff2e66a40629de6759d3a3d6d8f", "id": 3, "kind": "http", "ok": true}} |
| `crates/afudm-api/src/lib.rs:41` | `/add_blob` / null | {"status": 200, "json": {"ok": true, "id": 4, "gid": "local:f82a72ea649940cdbee6ba4a17eab71b", "kind": "http"}} | {"status": 200, "json": {"gid": "local:9da6cb84b5414c3cb68dd38aa19bc304", "id": 4, "kind": "http", "ok": true}} |
| `crates/afudm-api/src/lib.rs:41` | `/add_blob` / bool | {"status": 200, "json": {"ok": true, "id": 5, "gid": "local:a2bbbce1db8c4cda8df6caec510bebd6", "kind": "http"}} | {"status": 200, "json": {"gid": "local:79cdd8e55f4748298a403bed636ae0a4", "id": 5, "kind": "http", "ok": true}} |
| `crates/afudm-api/src/lib.rs:41` | `/add_blob` / empty | {"status": 200, "json": {"ok": true, "id": 6, "gid": "local:03e1fb4d7ffc40a983aba11ab41d1e62", "kind": "http"}} | {"status": 200, "json": {"gid": "local:75a8ca9c86694015b53690dbe2a0bdd4", "id": 6, "kind": "http", "ok": true}} |
| `crates/afudm-api/src/lib.rs:41` | `/add_blob` / wrong_types | {"status": 200, "json": {"ok": true, "id": 7, "gid": "local:e6833712786e4f0681cc881585e4cf4a", "kind": "http"}} | {"status": 200, "json": {"gid": "local:410ed675482e4d238289d4345d5d1c8e", "id": 7, "kind": "http", "ok": true}} |
| `crates/afudm-api/src/lib.rs:41` | `/add_blob` / unicode | {"status": 200, "json": {"ok": true, "id": 8, "gid": "local:9e51cc075daa46d49384eb52063c1bd0", "kind": "http"}} | {"status": 200, "json": {"gid": "local:19e49313b17f4712b7685118da15f5a3", "id": 8, "kind": "http", "ok": true}} |
| `crates/afudm-api/src/lib.rs:41` | `/add_blob` / traversal | {"status": 200, "json": {"ok": true, "id": 9, "gid": "local:e7601f4de6c047138b82f28f7369d5f4", "kind": "http"}} | {"status": 200, "json": {"gid": "local:73326870d0bb4780a986f890c3092a89", "id": 9, "kind": "http", "ok": true}} |
| `crates/afudm-api/src/lib.rs:41` | `/add_blob` / file | {"status": 200, "json": {"ok": true, "id": 10, "gid": "local:81ce18e104594a67813d4c526d6b3cbe", "kind": "http"}} | {"status": 200, "json": {"gid": "local:578c3f6333a04348a2a71df179d0529c", "id": 10, "kind": "http", "ok": true}} |
| `crates/afudm-api/src/lib.rs:41` | `/add_blob` / javascript | {"status": 200, "json": {"ok": true, "id": 11, "gid": "local:a3100046ad1d43a581f35fc100463daa", "kind": "http"}} | {"status": 200, "json": {"gid": "local:4b066bf7ae1d4cb89670c9c9ddad3c78", "id": 11, "kind": "http", "ok": true}} |
| `crates/afudm-api/src/lib.rs:41` | `/add_blob` / wrong_origin | {"status": 200, "json": {"ok": true, "id": 12, "gid": "local:aff0e938e17444fd8d581edf08cb2c09", "kind": "http"}} | {"status": 200, "json": {"gid": "local:d4087916326142b2b3bf5682c34d59e9", "id": 12, "kind": "http", "ok": true}} |
| `crates/afudm-extras/src/g2/mod.rs:99` | `/eklenti` / broken_json | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek okunamadi. Yeniden dene.", "error": "Istek okunamadi. Yeniden dene."}} | {"status": 400, "json": {"code": "BAD_REQUEST", "error": "gecersiz JSON govdesi", "message": "gecersiz JSON govdesi", "ok": false}} |
| `crates/afudm-extras/src/g2/mod.rs:99` | `/eklenti` / huge | {"status": 413, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "error": "Istek boyutu uygun degil. Daha kucuk bir istek gonder."}} | {"status": 413, "json": {"raw": "Failed to buffer the request body: length limit exceeded"}} |
| `crates/afudm-extras/src/g2/mod.rs:99` | `/eklenti` / list | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 400, "json": {"code": "BILINMEYEN_EYLEM", "error": "bilinmeyen eklenti eylemi", "message": "bilinmeyen eklenti eylemi", "ok": false}} |
| `crates/afudm-extras/src/g2/mod.rs:99` | `/eklenti` / null | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 400, "json": {"code": "BILINMEYEN_EYLEM", "error": "bilinmeyen eklenti eylemi", "message": "bilinmeyen eklenti eylemi", "ok": false}} |
| `crates/afudm-extras/src/g2/mod.rs:99` | `/eklenti` / bool | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 400, "json": {"code": "BILINMEYEN_EYLEM", "error": "bilinmeyen eklenti eylemi", "message": "bilinmeyen eklenti eylemi", "ok": false}} |
| `crates/afudm-extras/src/g2/mod.rs:102` | `/linkgrabber` / broken_json | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek okunamadi. Yeniden dene.", "error": "Istek okunamadi. Yeniden dene."}} | {"status": 400, "json": {"code": "BAD_REQUEST", "error": "gecersiz JSON govdesi", "message": "gecersiz JSON govdesi", "ok": false}} |
| `crates/afudm-extras/src/g2/mod.rs:102` | `/linkgrabber` / huge | {"status": 413, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "error": "Istek boyutu uygun degil. Daha kucuk bir istek gonder."}} | {"status": 413, "json": {"raw": "Failed to buffer the request body: length limit exceeded"}} |
| `crates/afudm-extras/src/g2/mod.rs:102` | `/linkgrabber` / list | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 400, "json": {"code": "BAD_REQUEST", "error": "metin gerekli", "message": "metin gerekli", "ok": false}} |
| `crates/afudm-extras/src/g2/mod.rs:102` | `/linkgrabber` / null | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 400, "json": {"code": "BAD_REQUEST", "error": "metin gerekli", "message": "metin gerekli", "ok": false}} |
| `crates/afudm-extras/src/g2/mod.rs:102` | `/linkgrabber` / bool | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 400, "json": {"code": "BAD_REQUEST", "error": "metin gerekli", "message": "metin gerekli", "ok": false}} |
| `crates/afudm-extras/src/g1/mod.rs:32` | `/reliability/backup` / broken_json | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek okunamadi. Yeniden dene.", "error": "Istek okunamadi. Yeniden dene."}} | {"status": 200, "json": {"created_at": 1792295702.0984185, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\backups\\afudm-20261018-065502-manual.zip"}} |
| `crates/afudm-extras/src/g1/mod.rs:32` | `/reliability/backup` / huge | {"status": 413, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "error": "Istek boyutu uygun degil. Daha kucuk bir istek gonder."}} | {"status": 200, "json": {"created_at": 1792295702.1298716, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\backups\\afudm-20261018-065502-manual.zip"}} |
| `crates/afudm-extras/src/g1/mod.rs:32` | `/reliability/backup` / list | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 200, "json": {"created_at": 1792295702.1583357, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\backups\\afudm-20261018-065502-manual.zip"}} |
| `crates/afudm-extras/src/g1/mod.rs:32` | `/reliability/backup` / null | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 200, "json": {"created_at": 1792295702.2101948, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\backups\\afudm-20261018-065502-manual.zip"}} |
| `crates/afudm-extras/src/g1/mod.rs:32` | `/reliability/backup` / bool | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 200, "json": {"created_at": 1792295702.2578998, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\backups\\afudm-20261018-065502-manual.zip"}} |
| `crates/afudm-extras/src/g1/mod.rs:32` | `/reliability/backup` / empty | {"status": 200, "json": {"ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\data\\backups\\afudm-20261018-065502-manual.zip", "created_at": 1792295702.2958653}} | {"status": 200, "json": {"created_at": 1792295702.331771, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\backups\\afudm-20261018-065502-manual.zip"}} |
| `crates/afudm-extras/src/g1/mod.rs:32` | `/reliability/backup` / wrong_types | {"status": 200, "json": {"ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\data\\backups\\afudm-20261018-065502-manual.zip", "created_at": 1792295702.3552613}} | {"status": 200, "json": {"created_at": 1792295702.3837242, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\backups\\afudm-20261018-065502-manual.zip"}} |
| `crates/afudm-extras/src/g1/mod.rs:32` | `/reliability/backup` / unicode | {"status": 200, "json": {"ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\data\\backups\\afudm-20261018-065502-manual.zip", "created_at": 1792295702.407072}} | {"status": 200, "json": {"created_at": 1792295702.4495351, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\backups\\afudm-20261018-065502-manual.zip"}} |
| `crates/afudm-extras/src/g1/mod.rs:32` | `/reliability/backup` / traversal | {"status": 200, "json": {"ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\data\\backups\\afudm-20261018-065502-manual.zip", "created_at": 1792295702.4673007}} | {"status": 200, "json": {"created_at": 1792295702.4980776, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\backups\\afudm-20261018-065502-manual.zip"}} |
| `crates/afudm-extras/src/g1/mod.rs:32` | `/reliability/backup` / file | {"status": 200, "json": {"ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\data\\backups\\afudm-20261018-065502-manual.zip", "created_at": 1792295702.515751}} | {"status": 200, "json": {"created_at": 1792295702.5545976, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\backups\\afudm-20261018-065502-manual.zip"}} |
| `crates/afudm-extras/src/g1/mod.rs:32` | `/reliability/backup` / javascript | {"status": 200, "json": {"ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\data\\backups\\afudm-20261018-065502-manual.zip", "created_at": 1792295702.5761075}} | {"status": 200, "json": {"created_at": 1792295702.6195269, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\backups\\afudm-20261018-065502-manual.zip"}} |
| `crates/afudm-extras/src/g1/mod.rs:32` | `/reliability/backup` / wrong_origin | {"status": 200, "json": {"ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\data\\backups\\afudm-20261018-065502-manual.zip", "created_at": 1792295702.6598084}} | {"status": 200, "json": {"created_at": 1792295702.6881754, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\backups\\afudm-20261018-065502-manual.zip"}} |
| `crates/afudm-extras/src/g1/mod.rs:40` | `/reliability/diagnostics-export` / broken_json | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek okunamadi. Yeniden dene.", "error": "Istek okunamadi. Yeniden dene."}} | {"status": 200, "json": {"masked": true, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\diagnostics\\afudm-diagnostics-20261018-065502.json"}} |
| `crates/afudm-extras/src/g1/mod.rs:40` | `/reliability/diagnostics-export` / huge | {"status": 413, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "error": "Istek boyutu uygun degil. Daha kucuk bir istek gonder."}} | {"status": 200, "json": {"masked": true, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\diagnostics\\afudm-diagnostics-20261018-065502.json"}} |
| `crates/afudm-extras/src/g1/mod.rs:40` | `/reliability/diagnostics-export` / list | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 200, "json": {"masked": true, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\diagnostics\\afudm-diagnostics-20261018-065502.json"}} |
| `crates/afudm-extras/src/g1/mod.rs:40` | `/reliability/diagnostics-export` / null | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 200, "json": {"masked": true, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\diagnostics\\afudm-diagnostics-20261018-065502.json"}} |
| `crates/afudm-extras/src/g1/mod.rs:40` | `/reliability/diagnostics-export` / bool | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 200, "json": {"masked": true, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\diagnostics\\afudm-diagnostics-20261018-065502.json"}} |
| `crates/afudm-extras/src/g1/mod.rs:40` | `/reliability/diagnostics-export` / empty | {"status": 200, "json": {"ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\data\\diagnostics\\afudm-diagnostics-20261018-065502.json", "masked": true}} | {"status": 200, "json": {"masked": true, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\diagnostics\\afudm-diagnostics-20261018-065502.json"}} |
| `crates/afudm-extras/src/g1/mod.rs:40` | `/reliability/diagnostics-export` / wrong_types | {"status": 200, "json": {"ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\data\\diagnostics\\afudm-diagnostics-20261018-065502.json", "masked": true}} | {"status": 200, "json": {"masked": true, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\diagnostics\\afudm-diagnostics-20261018-065502.json"}} |
| `crates/afudm-extras/src/g1/mod.rs:40` | `/reliability/diagnostics-export` / unicode | {"status": 200, "json": {"ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\data\\diagnostics\\afudm-diagnostics-20261018-065502.json", "masked": true}} | {"status": 200, "json": {"masked": true, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\diagnostics\\afudm-diagnostics-20261018-065502.json"}} |
| `crates/afudm-extras/src/g1/mod.rs:40` | `/reliability/diagnostics-export` / traversal | {"status": 200, "json": {"ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\data\\diagnostics\\afudm-diagnostics-20261018-065503.json", "masked": true}} | {"status": 200, "json": {"masked": true, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\diagnostics\\afudm-diagnostics-20261018-065503.json"}} |
| `crates/afudm-extras/src/g1/mod.rs:40` | `/reliability/diagnostics-export` / file | {"status": 200, "json": {"ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\data\\diagnostics\\afudm-diagnostics-20261018-065503.json", "masked": true}} | {"status": 200, "json": {"masked": true, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\diagnostics\\afudm-diagnostics-20261018-065503.json"}} |
| `crates/afudm-extras/src/g1/mod.rs:40` | `/reliability/diagnostics-export` / javascript | {"status": 200, "json": {"ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\data\\diagnostics\\afudm-diagnostics-20261018-065503.json", "masked": true}} | {"status": 200, "json": {"masked": true, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\diagnostics\\afudm-diagnostics-20261018-065503.json"}} |
| `crates/afudm-extras/src/g1/mod.rs:40` | `/reliability/diagnostics-export` / wrong_origin | {"status": 200, "json": {"ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\data\\diagnostics\\afudm-diagnostics-20261018-065503.json", "masked": true}} | {"status": 200, "json": {"masked": true, "ok": true, "path": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\data\\diagnostics\\afudm-diagnostics-20261018-065503.json"}} |
| `crates/afudm-extras/src/g1/mod.rs:36` | `/reliability/diagnostics-preview` / broken_json | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek okunamadi. Yeniden dene.", "error": "Istek okunamadi. Yeniden dene."}} | {"status": 200, "json": {"masked": true, "ok": true, "preview": {"engines": {"aria2c": {"boyut_mb": 5.4, "indirme_boyutu_mb": 3, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "indirme motoru", "sistem_yolu": "", "var": true, "zorunlu": true}, "cloudflared": {"boyut_mb": 0.0, "indirme_boyutu_mb": 21, "kaynak": "yok", "kullanilabilir": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "sistem_yolu": "", "var": false, "zorunlu": false}, "ffmpeg": {"boyut_mb": 0.0, "indirme_boyutu_mb": 164, "kaynak": "sistem", "kullanilabilir": true, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe", "var": false, "zorunlu": false}, "yt-dlp": {"boyut_mb": 17.0, "indirme_boyutu_mb": 17, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "sistem_yolu": "", "var": true, "zorunlu": false}}, "events": [{"at": 1792295641.6600914, "gid": null, "id": 20, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6481314, "gid": null, "id": 19, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6415212, "gid": null, "id": 18, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6348512, "gid": null, "id": 17, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6275692, "gid": null, "id": 16, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6081815, "gid": null, "id": 15, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6014893, "gid": null, "id": 14, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.487938, "gid": null, "id": 13, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4605694, "gid": null, "id": 12, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4388492, "gid": null, "id": 11, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4180868, "gid": null, "id": 10, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.396718, "gid": null, "id": 9, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3762705, "gid": null, "id": 8, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.357367, "gid": null, "id": 7, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3378294, "gid": null, "id": 6, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3187404, "gid": null, "id": 5, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.296393, "gid": null, "id": 4, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.1642544, "gid": null, "id": 3, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.0932064, "gid": "bd60694ebaeaed63", "id": 2, "level": "info", "message": "basladi [http]: 😀"}, {"at": 1792295640.6857622, "gid": null, "id": 1, "level": "info", "message": "AfuDM basladi"}], "generated_at": 1792295703.3008418, "integrity": {"action": "none", "checked_at": 1792295703.3011367, "details": ["ok"], "ok": true, "status": "ok"}, "settings": {"ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "video_quality": "best", "windows_notifications": false}}}} |
| `crates/afudm-extras/src/g1/mod.rs:36` | `/reliability/diagnostics-preview` / huge | {"status": 413, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "error": "Istek boyutu uygun degil. Daha kucuk bir istek gonder."}} | {"status": 200, "json": {"masked": true, "ok": true, "preview": {"engines": {"aria2c": {"boyut_mb": 5.4, "indirme_boyutu_mb": 3, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "indirme motoru", "sistem_yolu": "", "var": true, "zorunlu": true}, "cloudflared": {"boyut_mb": 0.0, "indirme_boyutu_mb": 21, "kaynak": "yok", "kullanilabilir": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "sistem_yolu": "", "var": false, "zorunlu": false}, "ffmpeg": {"boyut_mb": 0.0, "indirme_boyutu_mb": 164, "kaynak": "sistem", "kullanilabilir": true, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe", "var": false, "zorunlu": false}, "yt-dlp": {"boyut_mb": 17.0, "indirme_boyutu_mb": 17, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "sistem_yolu": "", "var": true, "zorunlu": false}}, "events": [{"at": 1792295641.6600914, "gid": null, "id": 20, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6481314, "gid": null, "id": 19, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6415212, "gid": null, "id": 18, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6348512, "gid": null, "id": 17, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6275692, "gid": null, "id": 16, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6081815, "gid": null, "id": 15, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6014893, "gid": null, "id": 14, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.487938, "gid": null, "id": 13, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4605694, "gid": null, "id": 12, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4388492, "gid": null, "id": 11, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4180868, "gid": null, "id": 10, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.396718, "gid": null, "id": 9, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3762705, "gid": null, "id": 8, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.357367, "gid": null, "id": 7, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3378294, "gid": null, "id": 6, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3187404, "gid": null, "id": 5, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.296393, "gid": null, "id": 4, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.1642544, "gid": null, "id": 3, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.0932064, "gid": "bd60694ebaeaed63", "id": 2, "level": "info", "message": "basladi [http]: 😀"}, {"at": 1792295640.6857622, "gid": null, "id": 1, "level": "info", "message": "AfuDM basladi"}], "generated_at": 1792295703.3479245, "integrity": {"action": "none", "checked_at": 1792295703.3482754, "details": ["ok"], "ok": true, "status": "ok"}, "settings": {"ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "video_quality": "best", "windows_notifications": false}}}} |
| `crates/afudm-extras/src/g1/mod.rs:36` | `/reliability/diagnostics-preview` / list | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 200, "json": {"masked": true, "ok": true, "preview": {"engines": {"aria2c": {"boyut_mb": 5.4, "indirme_boyutu_mb": 3, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "indirme motoru", "sistem_yolu": "", "var": true, "zorunlu": true}, "cloudflared": {"boyut_mb": 0.0, "indirme_boyutu_mb": 21, "kaynak": "yok", "kullanilabilir": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "sistem_yolu": "", "var": false, "zorunlu": false}, "ffmpeg": {"boyut_mb": 0.0, "indirme_boyutu_mb": 164, "kaynak": "sistem", "kullanilabilir": true, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe", "var": false, "zorunlu": false}, "yt-dlp": {"boyut_mb": 17.0, "indirme_boyutu_mb": 17, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "sistem_yolu": "", "var": true, "zorunlu": false}}, "events": [{"at": 1792295641.6600914, "gid": null, "id": 20, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6481314, "gid": null, "id": 19, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6415212, "gid": null, "id": 18, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6348512, "gid": null, "id": 17, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6275692, "gid": null, "id": 16, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6081815, "gid": null, "id": 15, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6014893, "gid": null, "id": 14, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.487938, "gid": null, "id": 13, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4605694, "gid": null, "id": 12, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4388492, "gid": null, "id": 11, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4180868, "gid": null, "id": 10, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.396718, "gid": null, "id": 9, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3762705, "gid": null, "id": 8, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.357367, "gid": null, "id": 7, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3378294, "gid": null, "id": 6, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3187404, "gid": null, "id": 5, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.296393, "gid": null, "id": 4, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.1642544, "gid": null, "id": 3, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.0932064, "gid": "bd60694ebaeaed63", "id": 2, "level": "info", "message": "basladi [http]: 😀"}, {"at": 1792295640.6857622, "gid": null, "id": 1, "level": "info", "message": "AfuDM basladi"}], "generated_at": 1792295703.3567793, "integrity": {"action": "none", "checked_at": 1792295703.3570473, "details": ["ok"], "ok": true, "status": "ok"}, "settings": {"ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "video_quality": "best", "windows_notifications": false}}}} |
| `crates/afudm-extras/src/g1/mod.rs:36` | `/reliability/diagnostics-preview` / null | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 200, "json": {"masked": true, "ok": true, "preview": {"engines": {"aria2c": {"boyut_mb": 5.4, "indirme_boyutu_mb": 3, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "indirme motoru", "sistem_yolu": "", "var": true, "zorunlu": true}, "cloudflared": {"boyut_mb": 0.0, "indirme_boyutu_mb": 21, "kaynak": "yok", "kullanilabilir": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "sistem_yolu": "", "var": false, "zorunlu": false}, "ffmpeg": {"boyut_mb": 0.0, "indirme_boyutu_mb": 164, "kaynak": "sistem", "kullanilabilir": true, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe", "var": false, "zorunlu": false}, "yt-dlp": {"boyut_mb": 17.0, "indirme_boyutu_mb": 17, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "sistem_yolu": "", "var": true, "zorunlu": false}}, "events": [{"at": 1792295641.6600914, "gid": null, "id": 20, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6481314, "gid": null, "id": 19, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6415212, "gid": null, "id": 18, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6348512, "gid": null, "id": 17, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6275692, "gid": null, "id": 16, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6081815, "gid": null, "id": 15, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6014893, "gid": null, "id": 14, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.487938, "gid": null, "id": 13, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4605694, "gid": null, "id": 12, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4388492, "gid": null, "id": 11, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4180868, "gid": null, "id": 10, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.396718, "gid": null, "id": 9, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3762705, "gid": null, "id": 8, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.357367, "gid": null, "id": 7, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3378294, "gid": null, "id": 6, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3187404, "gid": null, "id": 5, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.296393, "gid": null, "id": 4, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.1642544, "gid": null, "id": 3, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.0932064, "gid": "bd60694ebaeaed63", "id": 2, "level": "info", "message": "basladi [http]: 😀"}, {"at": 1792295640.6857622, "gid": null, "id": 1, "level": "info", "message": "AfuDM basladi"}], "generated_at": 1792295703.364514, "integrity": {"action": "none", "checked_at": 1792295703.3647707, "details": ["ok"], "ok": true, "status": "ok"}, "settings": {"ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "video_quality": "best", "windows_notifications": false}}}} |
| `crates/afudm-extras/src/g1/mod.rs:36` | `/reliability/diagnostics-preview` / bool | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 200, "json": {"masked": true, "ok": true, "preview": {"engines": {"aria2c": {"boyut_mb": 5.4, "indirme_boyutu_mb": 3, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "indirme motoru", "sistem_yolu": "", "var": true, "zorunlu": true}, "cloudflared": {"boyut_mb": 0.0, "indirme_boyutu_mb": 21, "kaynak": "yok", "kullanilabilir": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "sistem_yolu": "", "var": false, "zorunlu": false}, "ffmpeg": {"boyut_mb": 0.0, "indirme_boyutu_mb": 164, "kaynak": "sistem", "kullanilabilir": true, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe", "var": false, "zorunlu": false}, "yt-dlp": {"boyut_mb": 17.0, "indirme_boyutu_mb": 17, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "sistem_yolu": "", "var": true, "zorunlu": false}}, "events": [{"at": 1792295641.6600914, "gid": null, "id": 20, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6481314, "gid": null, "id": 19, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6415212, "gid": null, "id": 18, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6348512, "gid": null, "id": 17, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6275692, "gid": null, "id": 16, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6081815, "gid": null, "id": 15, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6014893, "gid": null, "id": 14, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.487938, "gid": null, "id": 13, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4605694, "gid": null, "id": 12, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4388492, "gid": null, "id": 11, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4180868, "gid": null, "id": 10, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.396718, "gid": null, "id": 9, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3762705, "gid": null, "id": 8, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.357367, "gid": null, "id": 7, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3378294, "gid": null, "id": 6, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3187404, "gid": null, "id": 5, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.296393, "gid": null, "id": 4, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.1642544, "gid": null, "id": 3, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.0932064, "gid": "bd60694ebaeaed63", "id": 2, "level": "info", "message": "basladi [http]: 😀"}, {"at": 1792295640.6857622, "gid": null, "id": 1, "level": "info", "message": "AfuDM basladi"}], "generated_at": 1792295703.3729584, "integrity": {"action": "none", "checked_at": 1792295703.3733163, "details": ["ok"], "ok": true, "status": "ok"}, "settings": {"ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "video_quality": "best", "windows_notifications": false}}}} |
| `crates/afudm-extras/src/g1/mod.rs:36` | `/reliability/diagnostics-preview` / empty | {"status": 200, "json": {"ok": true, "preview": {"generated_at": 1792295703.3802056, "integrity": {"ok": true, "status": "ok", "details": ["ok"], "action": "none", "checked_at": 1792295703.3802056}, "engines": {"aria2c": {"var": true, "kaynak": "paket", "sistem_yolu": "", "kullanilabilir": true, "boyut_mb": 5.4, "zorunlu": true, "ne_icin": "indirme motoru", "indirme_boyutu_mb": 3}, "yt-dlp": {"var": true, "kaynak": "paket", "sistem_yolu": "", "kullanilabilir": true, "boyut_mb": 17.0, "zorunlu": false, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "indirme_boyutu_mb": 17}, "ffmpeg": {"var": false, "kaynak": "sistem", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.EXE", "kullanilabilir": true, "boyut_mb": 0, "zorunlu": false, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "indirme_boyutu_mb": 164}, "cloudflared": {"var": false, "kaynak": "yok", "sistem_yolu": "", "kullanilabilir": false, "boyut_mb": 0, "zorunlu": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "indirme_boyutu_mb": 21}}, "settings": {"language": "auto", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\downloads", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": false, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": false, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": false, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": false, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 63009, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "guncelleme_otomatik": false, "telefon_acik": false, "auto_accept_migrated": true}, "events": [{"id": 34, "at": 1792295641.6565943, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 33, "at": 1792295641.644593, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 32, "at": 1792295641.6380763, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 31, "at": 1792295641.6310756, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 30, "at": 1792295641.611062, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 29, "at": 1792295641.6045454, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 28, "at": 1792295641.597545, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 27, "at": 1792295641.476859, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 26, "at": 1792295641.4488559, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 25, "at": 1792295641.4282951, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 24, "at": 1792295641.4072814, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 23, "at": 1792295641.3857253, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 22, "at": 1792295641.3667026, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 21, "at": 1792295641.3472717, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 20, "at": 1792295641.3272588, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 19, "at": 1792295641.3082979, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 18, "at": 1792295641.1937916, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 17, "at": 1792295641.1531746, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 16, "at": 1792295641.141094, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 15, "at": 1792295641.1364522, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 14, "at": 1792295641.1313386, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 13, "at": 1792295641.1249926, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 12, "at": 1792295641.1059904, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali", "gid": null}, {"id": 11, "at": 1792295641.100989, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali", "gid": null}, {"id": 10, "at": 1792295641.096988, "level": "error", "message": "Tarayici devretme istegi reddedildi: hedef klasor indirme kokunun disinda", "gid": null}, {"id": 9, "at": 1792295641.0543792, "level": "info", "message": "basladi [http]: 😀", "gid": "aa7bd39129066188"}, {"id": 8, "at": 1792295641.0403295, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 7, "at": 1792295641.035283, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 6, "at": 1792295641.0312836, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 5, "at": 1792295641.0142696, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 4, "at": 1792295641.0086718, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 3, "at": 1792295641.004156, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "gid": null}, {"id": 2, "at": 1792295640.9991634, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek okunamadi. Yeniden dene.", "gid": null}, {"id": 1, "at": 1792295639.1851501, "level": "info", "message": "AfuDM basladi", "gid": null}]}, "masked": true}} | {"status": 200, "json": {"masked": true, "ok": true, "preview": {"engines": {"aria2c": {"boyut_mb": 5.4, "indirme_boyutu_mb": 3, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "indirme motoru", "sistem_yolu": "", "var": true, "zorunlu": true}, "cloudflared": {"boyut_mb": 0.0, "indirme_boyutu_mb": 21, "kaynak": "yok", "kullanilabilir": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "sistem_yolu": "", "var": false, "zorunlu": false}, "ffmpeg": {"boyut_mb": 0.0, "indirme_boyutu_mb": 164, "kaynak": "sistem", "kullanilabilir": true, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe", "var": false, "zorunlu": false}, "yt-dlp": {"boyut_mb": 17.0, "indirme_boyutu_mb": 17, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "sistem_yolu": "", "var": true, "zorunlu": false}}, "events": [{"at": 1792295641.6600914, "gid": null, "id": 20, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6481314, "gid": null, "id": 19, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6415212, "gid": null, "id": 18, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6348512, "gid": null, "id": 17, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6275692, "gid": null, "id": 16, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6081815, "gid": null, "id": 15, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6014893, "gid": null, "id": 14, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.487938, "gid": null, "id": 13, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4605694, "gid": null, "id": 12, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4388492, "gid": null, "id": 11, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4180868, "gid": null, "id": 10, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.396718, "gid": null, "id": 9, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3762705, "gid": null, "id": 8, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.357367, "gid": null, "id": 7, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3378294, "gid": null, "id": 6, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3187404, "gid": null, "id": 5, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.296393, "gid": null, "id": 4, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.1642544, "gid": null, "id": 3, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.0932064, "gid": "bd60694ebaeaed63", "id": 2, "level": "info", "message": "basladi [http]: 😀"}, {"at": 1792295640.6857622, "gid": null, "id": 1, "level": "info", "message": "AfuDM basladi"}], "generated_at": 1792295703.411298, "integrity": {"action": "none", "checked_at": 1792295703.4117403, "details": ["ok"], "ok": true, "status": "ok"}, "settings": {"ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "video_quality": "best", "windows_notifications": false}}}} |
| `crates/afudm-extras/src/g1/mod.rs:36` | `/reliability/diagnostics-preview` / wrong_types | {"status": 200, "json": {"ok": true, "preview": {"generated_at": 1792295703.4186, "integrity": {"ok": true, "status": "ok", "details": ["ok"], "action": "none", "checked_at": 1792295703.4186}, "engines": {"aria2c": {"var": true, "kaynak": "paket", "sistem_yolu": "", "kullanilabilir": true, "boyut_mb": 5.4, "zorunlu": true, "ne_icin": "indirme motoru", "indirme_boyutu_mb": 3}, "yt-dlp": {"var": true, "kaynak": "paket", "sistem_yolu": "", "kullanilabilir": true, "boyut_mb": 17.0, "zorunlu": false, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "indirme_boyutu_mb": 17}, "ffmpeg": {"var": false, "kaynak": "sistem", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.EXE", "kullanilabilir": true, "boyut_mb": 0, "zorunlu": false, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "indirme_boyutu_mb": 164}, "cloudflared": {"var": false, "kaynak": "yok", "sistem_yolu": "", "kullanilabilir": false, "boyut_mb": 0, "zorunlu": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "indirme_boyutu_mb": 21}}, "settings": {"language": "auto", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\downloads", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": false, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": false, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": false, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": false, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 63009, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "guncelleme_otomatik": false, "telefon_acik": false, "auto_accept_migrated": true}, "events": [{"id": 34, "at": 1792295641.6565943, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 33, "at": 1792295641.644593, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 32, "at": 1792295641.6380763, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 31, "at": 1792295641.6310756, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 30, "at": 1792295641.611062, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 29, "at": 1792295641.6045454, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 28, "at": 1792295641.597545, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 27, "at": 1792295641.476859, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 26, "at": 1792295641.4488559, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 25, "at": 1792295641.4282951, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 24, "at": 1792295641.4072814, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 23, "at": 1792295641.3857253, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 22, "at": 1792295641.3667026, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 21, "at": 1792295641.3472717, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 20, "at": 1792295641.3272588, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 19, "at": 1792295641.3082979, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 18, "at": 1792295641.1937916, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 17, "at": 1792295641.1531746, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 16, "at": 1792295641.141094, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 15, "at": 1792295641.1364522, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 14, "at": 1792295641.1313386, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 13, "at": 1792295641.1249926, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 12, "at": 1792295641.1059904, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali", "gid": null}, {"id": 11, "at": 1792295641.100989, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali", "gid": null}, {"id": 10, "at": 1792295641.096988, "level": "error", "message": "Tarayici devretme istegi reddedildi: hedef klasor indirme kokunun disinda", "gid": null}, {"id": 9, "at": 1792295641.0543792, "level": "info", "message": "basladi [http]: 😀", "gid": "aa7bd39129066188"}, {"id": 8, "at": 1792295641.0403295, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 7, "at": 1792295641.035283, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 6, "at": 1792295641.0312836, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 5, "at": 1792295641.0142696, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 4, "at": 1792295641.0086718, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 3, "at": 1792295641.004156, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "gid": null}, {"id": 2, "at": 1792295640.9991634, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek okunamadi. Yeniden dene.", "gid": null}, {"id": 1, "at": 1792295639.1851501, "level": "info", "message": "AfuDM basladi", "gid": null}]}, "masked": true}} | {"status": 200, "json": {"masked": true, "ok": true, "preview": {"engines": {"aria2c": {"boyut_mb": 5.4, "indirme_boyutu_mb": 3, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "indirme motoru", "sistem_yolu": "", "var": true, "zorunlu": true}, "cloudflared": {"boyut_mb": 0.0, "indirme_boyutu_mb": 21, "kaynak": "yok", "kullanilabilir": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "sistem_yolu": "", "var": false, "zorunlu": false}, "ffmpeg": {"boyut_mb": 0.0, "indirme_boyutu_mb": 164, "kaynak": "sistem", "kullanilabilir": true, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe", "var": false, "zorunlu": false}, "yt-dlp": {"boyut_mb": 17.0, "indirme_boyutu_mb": 17, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "sistem_yolu": "", "var": true, "zorunlu": false}}, "events": [{"at": 1792295641.6600914, "gid": null, "id": 20, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6481314, "gid": null, "id": 19, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6415212, "gid": null, "id": 18, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6348512, "gid": null, "id": 17, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6275692, "gid": null, "id": 16, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6081815, "gid": null, "id": 15, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6014893, "gid": null, "id": 14, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.487938, "gid": null, "id": 13, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4605694, "gid": null, "id": 12, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4388492, "gid": null, "id": 11, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4180868, "gid": null, "id": 10, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.396718, "gid": null, "id": 9, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3762705, "gid": null, "id": 8, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.357367, "gid": null, "id": 7, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3378294, "gid": null, "id": 6, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3187404, "gid": null, "id": 5, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.296393, "gid": null, "id": 4, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.1642544, "gid": null, "id": 3, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.0932064, "gid": "bd60694ebaeaed63", "id": 2, "level": "info", "message": "basladi [http]: 😀"}, {"at": 1792295640.6857622, "gid": null, "id": 1, "level": "info", "message": "AfuDM basladi"}], "generated_at": 1792295703.4523506, "integrity": {"action": "none", "checked_at": 1792295703.4527357, "details": ["ok"], "ok": true, "status": "ok"}, "settings": {"ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "video_quality": "best", "windows_notifications": false}}}} |
| `crates/afudm-extras/src/g1/mod.rs:36` | `/reliability/diagnostics-preview` / unicode | {"status": 200, "json": {"ok": true, "preview": {"generated_at": 1792295703.4725828, "integrity": {"ok": true, "status": "ok", "details": ["ok"], "action": "none", "checked_at": 1792295703.4725828}, "engines": {"aria2c": {"var": true, "kaynak": "paket", "sistem_yolu": "", "kullanilabilir": true, "boyut_mb": 5.4, "zorunlu": true, "ne_icin": "indirme motoru", "indirme_boyutu_mb": 3}, "yt-dlp": {"var": true, "kaynak": "paket", "sistem_yolu": "", "kullanilabilir": true, "boyut_mb": 17.0, "zorunlu": false, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "indirme_boyutu_mb": 17}, "ffmpeg": {"var": false, "kaynak": "sistem", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.EXE", "kullanilabilir": true, "boyut_mb": 0, "zorunlu": false, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "indirme_boyutu_mb": 164}, "cloudflared": {"var": false, "kaynak": "yok", "sistem_yolu": "", "kullanilabilir": false, "boyut_mb": 0, "zorunlu": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "indirme_boyutu_mb": 21}}, "settings": {"language": "auto", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\downloads", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": false, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": false, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": false, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": false, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 63009, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "guncelleme_otomatik": false, "telefon_acik": false, "auto_accept_migrated": true}, "events": [{"id": 34, "at": 1792295641.6565943, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 33, "at": 1792295641.644593, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 32, "at": 1792295641.6380763, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 31, "at": 1792295641.6310756, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 30, "at": 1792295641.611062, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 29, "at": 1792295641.6045454, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 28, "at": 1792295641.597545, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 27, "at": 1792295641.476859, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 26, "at": 1792295641.4488559, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 25, "at": 1792295641.4282951, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 24, "at": 1792295641.4072814, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 23, "at": 1792295641.3857253, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 22, "at": 1792295641.3667026, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 21, "at": 1792295641.3472717, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 20, "at": 1792295641.3272588, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 19, "at": 1792295641.3082979, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 18, "at": 1792295641.1937916, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 17, "at": 1792295641.1531746, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 16, "at": 1792295641.141094, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 15, "at": 1792295641.1364522, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 14, "at": 1792295641.1313386, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 13, "at": 1792295641.1249926, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 12, "at": 1792295641.1059904, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali", "gid": null}, {"id": 11, "at": 1792295641.100989, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali", "gid": null}, {"id": 10, "at": 1792295641.096988, "level": "error", "message": "Tarayici devretme istegi reddedildi: hedef klasor indirme kokunun disinda", "gid": null}, {"id": 9, "at": 1792295641.0543792, "level": "info", "message": "basladi [http]: 😀", "gid": "aa7bd39129066188"}, {"id": 8, "at": 1792295641.0403295, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 7, "at": 1792295641.035283, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 6, "at": 1792295641.0312836, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 5, "at": 1792295641.0142696, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 4, "at": 1792295641.0086718, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 3, "at": 1792295641.004156, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "gid": null}, {"id": 2, "at": 1792295640.9991634, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek okunamadi. Yeniden dene.", "gid": null}, {"id": 1, "at": 1792295639.1851501, "level": "info", "message": "AfuDM basladi", "gid": null}]}, "masked": true}} | {"status": 200, "json": {"masked": true, "ok": true, "preview": {"engines": {"aria2c": {"boyut_mb": 5.4, "indirme_boyutu_mb": 3, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "indirme motoru", "sistem_yolu": "", "var": true, "zorunlu": true}, "cloudflared": {"boyut_mb": 0.0, "indirme_boyutu_mb": 21, "kaynak": "yok", "kullanilabilir": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "sistem_yolu": "", "var": false, "zorunlu": false}, "ffmpeg": {"boyut_mb": 0.0, "indirme_boyutu_mb": 164, "kaynak": "sistem", "kullanilabilir": true, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe", "var": false, "zorunlu": false}, "yt-dlp": {"boyut_mb": 17.0, "indirme_boyutu_mb": 17, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "sistem_yolu": "", "var": true, "zorunlu": false}}, "events": [{"at": 1792295641.6600914, "gid": null, "id": 20, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6481314, "gid": null, "id": 19, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6415212, "gid": null, "id": 18, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6348512, "gid": null, "id": 17, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6275692, "gid": null, "id": 16, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6081815, "gid": null, "id": 15, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6014893, "gid": null, "id": 14, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.487938, "gid": null, "id": 13, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4605694, "gid": null, "id": 12, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4388492, "gid": null, "id": 11, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4180868, "gid": null, "id": 10, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.396718, "gid": null, "id": 9, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3762705, "gid": null, "id": 8, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.357367, "gid": null, "id": 7, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3378294, "gid": null, "id": 6, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3187404, "gid": null, "id": 5, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.296393, "gid": null, "id": 4, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.1642544, "gid": null, "id": 3, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.0932064, "gid": "bd60694ebaeaed63", "id": 2, "level": "info", "message": "basladi [http]: 😀"}, {"at": 1792295640.6857622, "gid": null, "id": 1, "level": "info", "message": "AfuDM basladi"}], "generated_at": 1792295703.5059469, "integrity": {"action": "none", "checked_at": 1792295703.5063386, "details": ["ok"], "ok": true, "status": "ok"}, "settings": {"ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "video_quality": "best", "windows_notifications": false}}}} |
| `crates/afudm-extras/src/g1/mod.rs:36` | `/reliability/diagnostics-preview` / traversal | {"status": 200, "json": {"ok": true, "preview": {"generated_at": 1792295703.5133345, "integrity": {"ok": true, "status": "ok", "details": ["ok"], "action": "none", "checked_at": 1792295703.5133345}, "engines": {"aria2c": {"var": true, "kaynak": "paket", "sistem_yolu": "", "kullanilabilir": true, "boyut_mb": 5.4, "zorunlu": true, "ne_icin": "indirme motoru", "indirme_boyutu_mb": 3}, "yt-dlp": {"var": true, "kaynak": "paket", "sistem_yolu": "", "kullanilabilir": true, "boyut_mb": 17.0, "zorunlu": false, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "indirme_boyutu_mb": 17}, "ffmpeg": {"var": false, "kaynak": "sistem", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.EXE", "kullanilabilir": true, "boyut_mb": 0, "zorunlu": false, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "indirme_boyutu_mb": 164}, "cloudflared": {"var": false, "kaynak": "yok", "sistem_yolu": "", "kullanilabilir": false, "boyut_mb": 0, "zorunlu": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "indirme_boyutu_mb": 21}}, "settings": {"language": "auto", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\downloads", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": false, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": false, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": false, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": false, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 63009, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "guncelleme_otomatik": false, "telefon_acik": false, "auto_accept_migrated": true}, "events": [{"id": 34, "at": 1792295641.6565943, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 33, "at": 1792295641.644593, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 32, "at": 1792295641.6380763, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 31, "at": 1792295641.6310756, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 30, "at": 1792295641.611062, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 29, "at": 1792295641.6045454, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 28, "at": 1792295641.597545, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 27, "at": 1792295641.476859, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 26, "at": 1792295641.4488559, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 25, "at": 1792295641.4282951, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 24, "at": 1792295641.4072814, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 23, "at": 1792295641.3857253, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 22, "at": 1792295641.3667026, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 21, "at": 1792295641.3472717, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 20, "at": 1792295641.3272588, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 19, "at": 1792295641.3082979, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 18, "at": 1792295641.1937916, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 17, "at": 1792295641.1531746, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 16, "at": 1792295641.141094, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 15, "at": 1792295641.1364522, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 14, "at": 1792295641.1313386, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 13, "at": 1792295641.1249926, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 12, "at": 1792295641.1059904, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali", "gid": null}, {"id": 11, "at": 1792295641.100989, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali", "gid": null}, {"id": 10, "at": 1792295641.096988, "level": "error", "message": "Tarayici devretme istegi reddedildi: hedef klasor indirme kokunun disinda", "gid": null}, {"id": 9, "at": 1792295641.0543792, "level": "info", "message": "basladi [http]: 😀", "gid": "aa7bd39129066188"}, {"id": 8, "at": 1792295641.0403295, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 7, "at": 1792295641.035283, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 6, "at": 1792295641.0312836, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 5, "at": 1792295641.0142696, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 4, "at": 1792295641.0086718, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 3, "at": 1792295641.004156, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "gid": null}, {"id": 2, "at": 1792295640.9991634, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek okunamadi. Yeniden dene.", "gid": null}, {"id": 1, "at": 1792295639.1851501, "level": "info", "message": "AfuDM basladi", "gid": null}]}, "masked": true}} | {"status": 200, "json": {"masked": true, "ok": true, "preview": {"engines": {"aria2c": {"boyut_mb": 5.4, "indirme_boyutu_mb": 3, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "indirme motoru", "sistem_yolu": "", "var": true, "zorunlu": true}, "cloudflared": {"boyut_mb": 0.0, "indirme_boyutu_mb": 21, "kaynak": "yok", "kullanilabilir": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "sistem_yolu": "", "var": false, "zorunlu": false}, "ffmpeg": {"boyut_mb": 0.0, "indirme_boyutu_mb": 164, "kaynak": "sistem", "kullanilabilir": true, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe", "var": false, "zorunlu": false}, "yt-dlp": {"boyut_mb": 17.0, "indirme_boyutu_mb": 17, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "sistem_yolu": "", "var": true, "zorunlu": false}}, "events": [{"at": 1792295641.6600914, "gid": null, "id": 20, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6481314, "gid": null, "id": 19, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6415212, "gid": null, "id": 18, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6348512, "gid": null, "id": 17, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6275692, "gid": null, "id": 16, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6081815, "gid": null, "id": 15, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6014893, "gid": null, "id": 14, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.487938, "gid": null, "id": 13, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4605694, "gid": null, "id": 12, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4388492, "gid": null, "id": 11, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4180868, "gid": null, "id": 10, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.396718, "gid": null, "id": 9, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3762705, "gid": null, "id": 8, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.357367, "gid": null, "id": 7, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3378294, "gid": null, "id": 6, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3187404, "gid": null, "id": 5, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.296393, "gid": null, "id": 4, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.1642544, "gid": null, "id": 3, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.0932064, "gid": "bd60694ebaeaed63", "id": 2, "level": "info", "message": "basladi [http]: 😀"}, {"at": 1792295640.6857622, "gid": null, "id": 1, "level": "info", "message": "AfuDM basladi"}], "generated_at": 1792295703.5462556, "integrity": {"action": "none", "checked_at": 1792295703.546563, "details": ["ok"], "ok": true, "status": "ok"}, "settings": {"ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "video_quality": "best", "windows_notifications": false}}}} |
| `crates/afudm-extras/src/g1/mod.rs:36` | `/reliability/diagnostics-preview` / file | {"status": 200, "json": {"ok": true, "preview": {"generated_at": 1792295703.5546763, "integrity": {"ok": true, "status": "ok", "details": ["ok"], "action": "none", "checked_at": 1792295703.5546763}, "engines": {"aria2c": {"var": true, "kaynak": "paket", "sistem_yolu": "", "kullanilabilir": true, "boyut_mb": 5.4, "zorunlu": true, "ne_icin": "indirme motoru", "indirme_boyutu_mb": 3}, "yt-dlp": {"var": true, "kaynak": "paket", "sistem_yolu": "", "kullanilabilir": true, "boyut_mb": 17.0, "zorunlu": false, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "indirme_boyutu_mb": 17}, "ffmpeg": {"var": false, "kaynak": "sistem", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.EXE", "kullanilabilir": true, "boyut_mb": 0, "zorunlu": false, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "indirme_boyutu_mb": 164}, "cloudflared": {"var": false, "kaynak": "yok", "sistem_yolu": "", "kullanilabilir": false, "boyut_mb": 0, "zorunlu": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "indirme_boyutu_mb": 21}}, "settings": {"language": "auto", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\downloads", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": false, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": false, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": false, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": false, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 63009, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "guncelleme_otomatik": false, "telefon_acik": false, "auto_accept_migrated": true}, "events": [{"id": 34, "at": 1792295641.6565943, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 33, "at": 1792295641.644593, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 32, "at": 1792295641.6380763, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 31, "at": 1792295641.6310756, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 30, "at": 1792295641.611062, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 29, "at": 1792295641.6045454, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 28, "at": 1792295641.597545, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 27, "at": 1792295641.476859, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 26, "at": 1792295641.4488559, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 25, "at": 1792295641.4282951, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 24, "at": 1792295641.4072814, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 23, "at": 1792295641.3857253, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 22, "at": 1792295641.3667026, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 21, "at": 1792295641.3472717, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 20, "at": 1792295641.3272588, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 19, "at": 1792295641.3082979, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 18, "at": 1792295641.1937916, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 17, "at": 1792295641.1531746, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 16, "at": 1792295641.141094, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 15, "at": 1792295641.1364522, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 14, "at": 1792295641.1313386, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 13, "at": 1792295641.1249926, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 12, "at": 1792295641.1059904, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali", "gid": null}, {"id": 11, "at": 1792295641.100989, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali", "gid": null}, {"id": 10, "at": 1792295641.096988, "level": "error", "message": "Tarayici devretme istegi reddedildi: hedef klasor indirme kokunun disinda", "gid": null}, {"id": 9, "at": 1792295641.0543792, "level": "info", "message": "basladi [http]: 😀", "gid": "aa7bd39129066188"}, {"id": 8, "at": 1792295641.0403295, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 7, "at": 1792295641.035283, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 6, "at": 1792295641.0312836, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 5, "at": 1792295641.0142696, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 4, "at": 1792295641.0086718, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 3, "at": 1792295641.004156, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "gid": null}, {"id": 2, "at": 1792295640.9991634, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek okunamadi. Yeniden dene.", "gid": null}, {"id": 1, "at": 1792295639.1851501, "level": "info", "message": "AfuDM basladi", "gid": null}]}, "masked": true}} | {"status": 200, "json": {"masked": true, "ok": true, "preview": {"engines": {"aria2c": {"boyut_mb": 5.4, "indirme_boyutu_mb": 3, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "indirme motoru", "sistem_yolu": "", "var": true, "zorunlu": true}, "cloudflared": {"boyut_mb": 0.0, "indirme_boyutu_mb": 21, "kaynak": "yok", "kullanilabilir": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "sistem_yolu": "", "var": false, "zorunlu": false}, "ffmpeg": {"boyut_mb": 0.0, "indirme_boyutu_mb": 164, "kaynak": "sistem", "kullanilabilir": true, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe", "var": false, "zorunlu": false}, "yt-dlp": {"boyut_mb": 17.0, "indirme_boyutu_mb": 17, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "sistem_yolu": "", "var": true, "zorunlu": false}}, "events": [{"at": 1792295641.6600914, "gid": null, "id": 20, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6481314, "gid": null, "id": 19, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6415212, "gid": null, "id": 18, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6348512, "gid": null, "id": 17, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6275692, "gid": null, "id": 16, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6081815, "gid": null, "id": 15, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6014893, "gid": null, "id": 14, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.487938, "gid": null, "id": 13, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4605694, "gid": null, "id": 12, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4388492, "gid": null, "id": 11, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4180868, "gid": null, "id": 10, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.396718, "gid": null, "id": 9, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3762705, "gid": null, "id": 8, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.357367, "gid": null, "id": 7, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3378294, "gid": null, "id": 6, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3187404, "gid": null, "id": 5, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.296393, "gid": null, "id": 4, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.1642544, "gid": null, "id": 3, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.0932064, "gid": "bd60694ebaeaed63", "id": 2, "level": "info", "message": "basladi [http]: 😀"}, {"at": 1792295640.6857622, "gid": null, "id": 1, "level": "info", "message": "AfuDM basladi"}], "generated_at": 1792295703.5990808, "integrity": {"action": "none", "checked_at": 1792295703.599559, "details": ["ok"], "ok": true, "status": "ok"}, "settings": {"ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "video_quality": "best", "windows_notifications": false}}}} |
| `crates/afudm-extras/src/g1/mod.rs:36` | `/reliability/diagnostics-preview` / javascript | {"status": 200, "json": {"ok": true, "preview": {"generated_at": 1792295703.6064963, "integrity": {"ok": true, "status": "ok", "details": ["ok"], "action": "none", "checked_at": 1792295703.6064963}, "engines": {"aria2c": {"var": true, "kaynak": "paket", "sistem_yolu": "", "kullanilabilir": true, "boyut_mb": 5.4, "zorunlu": true, "ne_icin": "indirme motoru", "indirme_boyutu_mb": 3}, "yt-dlp": {"var": true, "kaynak": "paket", "sistem_yolu": "", "kullanilabilir": true, "boyut_mb": 17.0, "zorunlu": false, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "indirme_boyutu_mb": 17}, "ffmpeg": {"var": false, "kaynak": "sistem", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.EXE", "kullanilabilir": true, "boyut_mb": 0, "zorunlu": false, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "indirme_boyutu_mb": 164}, "cloudflared": {"var": false, "kaynak": "yok", "sistem_yolu": "", "kullanilabilir": false, "boyut_mb": 0, "zorunlu": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "indirme_boyutu_mb": 21}}, "settings": {"language": "auto", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\downloads", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": false, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": false, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": false, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": false, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 63009, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "guncelleme_otomatik": false, "telefon_acik": false, "auto_accept_migrated": true}, "events": [{"id": 34, "at": 1792295641.6565943, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 33, "at": 1792295641.644593, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 32, "at": 1792295641.6380763, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 31, "at": 1792295641.6310756, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 30, "at": 1792295641.611062, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 29, "at": 1792295641.6045454, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 28, "at": 1792295641.597545, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 27, "at": 1792295641.476859, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 26, "at": 1792295641.4488559, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 25, "at": 1792295641.4282951, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 24, "at": 1792295641.4072814, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 23, "at": 1792295641.3857253, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 22, "at": 1792295641.3667026, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 21, "at": 1792295641.3472717, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 20, "at": 1792295641.3272588, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 19, "at": 1792295641.3082979, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 18, "at": 1792295641.1937916, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 17, "at": 1792295641.1531746, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 16, "at": 1792295641.141094, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 15, "at": 1792295641.1364522, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 14, "at": 1792295641.1313386, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 13, "at": 1792295641.1249926, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 12, "at": 1792295641.1059904, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali", "gid": null}, {"id": 11, "at": 1792295641.100989, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali", "gid": null}, {"id": 10, "at": 1792295641.096988, "level": "error", "message": "Tarayici devretme istegi reddedildi: hedef klasor indirme kokunun disinda", "gid": null}, {"id": 9, "at": 1792295641.0543792, "level": "info", "message": "basladi [http]: 😀", "gid": "aa7bd39129066188"}, {"id": 8, "at": 1792295641.0403295, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 7, "at": 1792295641.035283, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 6, "at": 1792295641.0312836, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 5, "at": 1792295641.0142696, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 4, "at": 1792295641.0086718, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 3, "at": 1792295641.004156, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "gid": null}, {"id": 2, "at": 1792295640.9991634, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek okunamadi. Yeniden dene.", "gid": null}, {"id": 1, "at": 1792295639.1851501, "level": "info", "message": "AfuDM basladi", "gid": null}]}, "masked": true}} | {"status": 200, "json": {"masked": true, "ok": true, "preview": {"engines": {"aria2c": {"boyut_mb": 5.4, "indirme_boyutu_mb": 3, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "indirme motoru", "sistem_yolu": "", "var": true, "zorunlu": true}, "cloudflared": {"boyut_mb": 0.0, "indirme_boyutu_mb": 21, "kaynak": "yok", "kullanilabilir": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "sistem_yolu": "", "var": false, "zorunlu": false}, "ffmpeg": {"boyut_mb": 0.0, "indirme_boyutu_mb": 164, "kaynak": "sistem", "kullanilabilir": true, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe", "var": false, "zorunlu": false}, "yt-dlp": {"boyut_mb": 17.0, "indirme_boyutu_mb": 17, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "sistem_yolu": "", "var": true, "zorunlu": false}}, "events": [{"at": 1792295641.6600914, "gid": null, "id": 20, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6481314, "gid": null, "id": 19, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6415212, "gid": null, "id": 18, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6348512, "gid": null, "id": 17, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6275692, "gid": null, "id": 16, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6081815, "gid": null, "id": 15, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6014893, "gid": null, "id": 14, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.487938, "gid": null, "id": 13, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4605694, "gid": null, "id": 12, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4388492, "gid": null, "id": 11, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4180868, "gid": null, "id": 10, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.396718, "gid": null, "id": 9, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3762705, "gid": null, "id": 8, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.357367, "gid": null, "id": 7, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3378294, "gid": null, "id": 6, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3187404, "gid": null, "id": 5, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.296393, "gid": null, "id": 4, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.1642544, "gid": null, "id": 3, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.0932064, "gid": "bd60694ebaeaed63", "id": 2, "level": "info", "message": "basladi [http]: 😀"}, {"at": 1792295640.6857622, "gid": null, "id": 1, "level": "info", "message": "AfuDM basladi"}], "generated_at": 1792295703.661711, "integrity": {"action": "none", "checked_at": 1792295703.6621876, "details": ["ok"], "ok": true, "status": "ok"}, "settings": {"ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "video_quality": "best", "windows_notifications": false}}}} |
| `crates/afudm-extras/src/g1/mod.rs:36` | `/reliability/diagnostics-preview` / wrong_origin | {"status": 200, "json": {"ok": true, "preview": {"generated_at": 1792295703.7399573, "integrity": {"ok": true, "status": "ok", "details": ["ok"], "action": "none", "checked_at": 1792295703.7399573}, "engines": {"aria2c": {"var": true, "kaynak": "paket", "sistem_yolu": "", "kullanilabilir": true, "boyut_mb": 5.4, "zorunlu": true, "ne_icin": "indirme motoru", "indirme_boyutu_mb": 3}, "yt-dlp": {"var": true, "kaynak": "paket", "sistem_yolu": "", "kullanilabilir": true, "boyut_mb": 17.0, "zorunlu": false, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "indirme_boyutu_mb": 17}, "ffmpeg": {"var": false, "kaynak": "sistem", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.EXE", "kullanilabilir": true, "boyut_mb": 0, "zorunlu": false, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "indirme_boyutu_mb": 164}, "cloudflared": {"var": false, "kaynak": "yok", "sistem_yolu": "", "kullanilabilir": false, "boyut_mb": 0, "zorunlu": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "indirme_boyutu_mb": 21}}, "settings": {"language": "auto", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\downloads", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": false, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": false, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": false, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": false, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 63009, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "guncelleme_otomatik": false, "telefon_acik": false, "auto_accept_migrated": true}, "events": [{"id": 34, "at": 1792295641.6565943, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 33, "at": 1792295641.644593, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 32, "at": 1792295641.6380763, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 31, "at": 1792295641.6310756, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 30, "at": 1792295641.611062, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 29, "at": 1792295641.6045454, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 28, "at": 1792295641.597545, "level": "error", "message": "Tarayici devretme hatasi: Tarayici devretme istegi basarisiz", "gid": null}, {"id": 27, "at": 1792295641.476859, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 26, "at": 1792295641.4488559, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 25, "at": 1792295641.4282951, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 24, "at": 1792295641.4072814, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 23, "at": 1792295641.3857253, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 22, "at": 1792295641.3667026, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 21, "at": 1792295641.3472717, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 20, "at": 1792295641.3272588, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 19, "at": 1792295641.3082979, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 18, "at": 1792295641.1937916, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 17, "at": 1792295641.1531746, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi.", "gid": null}, {"id": 16, "at": 1792295641.141094, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 15, "at": 1792295641.1364522, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 14, "at": 1792295641.1313386, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 13, "at": 1792295641.1249926, "level": "error", "message": "Tarayici devretme istegi reddedildi: gecersiz token", "gid": null}, {"id": 12, "at": 1792295641.1059904, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali", "gid": null}, {"id": 11, "at": 1792295641.100989, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: gecersiz baglanti: http(s), ftp, magnet ya da .torrent dosyasi olmali", "gid": null}, {"id": 10, "at": 1792295641.096988, "level": "error", "message": "Tarayici devretme istegi reddedildi: hedef klasor indirme kokunun disinda", "gid": null}, {"id": 9, "at": 1792295641.0543792, "level": "info", "message": "basladi [http]: 😀", "gid": "aa7bd39129066188"}, {"id": 8, "at": 1792295641.0403295, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 7, "at": 1792295641.035283, "level": "error", "message": "Tarayici devretme istegi reddedildi: ValueError: bos link", "gid": null}, {"id": 6, "at": 1792295641.0312836, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 5, "at": 1792295641.0142696, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 4, "at": 1792295641.0086718, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek bicimi uygun degil. Yeniden dene.", "gid": null}, {"id": 3, "at": 1792295641.004156, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "gid": null}, {"id": 2, "at": 1792295640.9991634, "level": "error", "message": "Tarayici devretme istegi reddedildi: Istek okunamadi. Yeniden dene.", "gid": null}, {"id": 1, "at": 1792295639.1851501, "level": "info", "message": "AfuDM basladi", "gid": null}]}, "masked": true}} | {"status": 200, "json": {"masked": true, "ok": true, "preview": {"engines": {"aria2c": {"boyut_mb": 5.4, "indirme_boyutu_mb": 3, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "indirme motoru", "sistem_yolu": "", "var": true, "zorunlu": true}, "cloudflared": {"boyut_mb": 0.0, "indirme_boyutu_mb": 21, "kaynak": "yok", "kullanilabilir": false, "ne_icin": "farkli aglardan guvenli dosya paylasimi", "sistem_yolu": "", "var": false, "zorunlu": false}, "ffmpeg": {"boyut_mb": 0.0, "indirme_boyutu_mb": 164, "kaynak": "sistem", "kullanilabilir": true, "ne_icin": "ses+video birlestirme (1080p ve ustu) ve mp3'e cevirme", "sistem_yolu": "C:\\Users\\afuuu\\AppData\\Local\\Microsoft\\WinGet\\Links\\ffmpeg.exe", "var": false, "zorunlu": false}, "yt-dlp": {"boyut_mb": 17.0, "indirme_boyutu_mb": 17, "kaynak": "paket", "kullanilabilir": true, "ne_icin": "video sitelerinden indirme (YouTube, Instagram, TikTok...)", "sistem_yolu": "", "var": true, "zorunlu": false}}, "events": [{"at": 1792295641.6600914, "gid": null, "id": 20, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6481314, "gid": null, "id": 19, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6415212, "gid": null, "id": 18, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6348512, "gid": null, "id": 17, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6275692, "gid": null, "id": 16, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6081815, "gid": null, "id": 15, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.6014893, "gid": null, "id": 14, "level": "error", "message": "Tarayici devretme hatasi"}, {"at": 1792295641.487938, "gid": null, "id": 13, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4605694, "gid": null, "id": 12, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4388492, "gid": null, "id": 11, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.4180868, "gid": null, "id": 10, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.396718, "gid": null, "id": 9, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3762705, "gid": null, "id": 8, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.357367, "gid": null, "id": 7, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3378294, "gid": null, "id": 6, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.3187404, "gid": null, "id": 5, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.296393, "gid": null, "id": 4, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.1642544, "gid": null, "id": 3, "level": "info", "message": "Tarayıcıdan gelen dosya kaydedildi."}, {"at": 1792295641.0932064, "gid": "bd60694ebaeaed63", "id": 2, "level": "info", "message": "basladi [http]: 😀"}, {"at": 1792295640.6857622, "gid": null, "id": 1, "level": "info", "message": "AfuDM basladi"}], "generated_at": 1792295703.7729692, "integrity": {"action": "none", "checked_at": 1792295703.7733514, "details": ["ok"], "ok": true, "status": "ok"}, "settings": {"ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "video_quality": "best", "windows_notifications": false}}}} |
| `crates/afudm-extras/src/g1/mod.rs:28` | `/reliability/integrity` / broken_json | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek okunamadi. Yeniden dene.", "error": "Istek okunamadi. Yeniden dene."}} | {"status": 200, "json": {"action": "none", "checked_at": 1792295703.8073635, "details": ["ok"], "ok": true, "status": "ok"}} |
| `crates/afudm-extras/src/g1/mod.rs:28` | `/reliability/integrity` / huge | {"status": 413, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "error": "Istek boyutu uygun degil. Daha kucuk bir istek gonder."}} | {"status": 200, "json": {"action": "none", "checked_at": 1792295703.8332283, "details": ["ok"], "ok": true, "status": "ok"}} |
| `crates/afudm-extras/src/g1/mod.rs:28` | `/reliability/integrity` / list | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 200, "json": {"action": "none", "checked_at": 1792295703.837962, "details": ["ok"], "ok": true, "status": "ok"}} |
| `crates/afudm-extras/src/g1/mod.rs:28` | `/reliability/integrity` / null | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 200, "json": {"action": "none", "checked_at": 1792295703.8410306, "details": ["ok"], "ok": true, "status": "ok"}} |
| `crates/afudm-extras/src/g1/mod.rs:28` | `/reliability/integrity` / bool | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 200, "json": {"action": "none", "checked_at": 1792295703.84411, "details": ["ok"], "ok": true, "status": "ok"}} |
| `crates/afudm-extras/src/g1/mod.rs:28` | `/reliability/integrity` / empty | {"status": 200, "json": {"ok": true, "status": "ok", "details": ["ok"], "action": "none", "checked_at": 1792295703.8452854}} | {"status": 200, "json": {"action": "none", "checked_at": 1792295703.8473477, "details": ["ok"], "ok": true, "status": "ok"}} |
| `crates/afudm-extras/src/g1/mod.rs:28` | `/reliability/integrity` / wrong_types | {"status": 200, "json": {"ok": true, "status": "ok", "details": ["ok"], "action": "none", "checked_at": 1792295703.8484626}} | {"status": 200, "json": {"action": "none", "checked_at": 1792295703.8510196, "details": ["ok"], "ok": true, "status": "ok"}} |
| `crates/afudm-extras/src/g1/mod.rs:28` | `/reliability/integrity` / unicode | {"status": 200, "json": {"ok": true, "status": "ok", "details": ["ok"], "action": "none", "checked_at": 1792295703.852296}} | {"status": 200, "json": {"action": "none", "checked_at": 1792295703.8545632, "details": ["ok"], "ok": true, "status": "ok"}} |
| `crates/afudm-extras/src/g1/mod.rs:28` | `/reliability/integrity` / traversal | {"status": 200, "json": {"ok": true, "status": "ok", "details": ["ok"], "action": "none", "checked_at": 1792295703.8798738}} | {"status": 200, "json": {"action": "none", "checked_at": 1792295703.882796, "details": ["ok"], "ok": true, "status": "ok"}} |
| `crates/afudm-extras/src/g1/mod.rs:28` | `/reliability/integrity` / file | {"status": 200, "json": {"ok": true, "status": "ok", "details": ["ok"], "action": "none", "checked_at": 1792295703.8838758}} | {"status": 200, "json": {"action": "none", "checked_at": 1792295703.8864639, "details": ["ok"], "ok": true, "status": "ok"}} |
| `crates/afudm-extras/src/g1/mod.rs:28` | `/reliability/integrity` / javascript | {"status": 200, "json": {"ok": true, "status": "ok", "details": ["ok"], "action": "none", "checked_at": 1792295703.8868754}} | {"status": 200, "json": {"action": "none", "checked_at": 1792295703.889378, "details": ["ok"], "ok": true, "status": "ok"}} |
| `crates/afudm-extras/src/g1/mod.rs:28` | `/reliability/integrity` / wrong_origin | {"status": 200, "json": {"ok": true, "status": "ok", "details": ["ok"], "action": "none", "checked_at": 1792295703.943826}} | {"status": 200, "json": {"action": "none", "checked_at": 1792295703.9600778, "details": ["ok"], "ok": true, "status": "ok"}} |
| `crates/afudm-extras/src/g2/mod.rs:97` | `/rules` / broken_json | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek okunamadi. Yeniden dene.", "error": "Istek okunamadi. Yeniden dene."}} | {"status": 400, "json": {"code": "BAD_REQUEST", "error": "gecersiz JSON govdesi", "message": "gecersiz JSON govdesi", "ok": false}} |
| `crates/afudm-extras/src/g2/mod.rs:97` | `/rules` / huge | {"status": 413, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "error": "Istek boyutu uygun degil. Daha kucuk bir istek gonder."}} | {"status": 413, "json": {"raw": "Failed to buffer the request body: length limit exceeded"}} |
| `crates/afudm-extras/src/g2/mod.rs:97` | `/rules` / list | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 400, "json": {"code": "BAD_REQUEST", "error": "rules liste olmali", "message": "rules liste olmali", "ok": false}} |
| `crates/afudm-extras/src/g2/mod.rs:97` | `/rules` / null | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 400, "json": {"code": "BAD_REQUEST", "error": "rules liste olmali", "message": "rules liste olmali", "ok": false}} |
| `crates/afudm-extras/src/g2/mod.rs:97` | `/rules` / bool | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 400, "json": {"code": "BAD_REQUEST", "error": "rules liste olmali", "message": "rules liste olmali", "ok": false}} |
| `crates/afudm-api/src/lib.rs:44` | `/settings` / empty | {"status": 200, "json": {"ok": true, "settings": {"language": "auto", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\downloads", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": false, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": false, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": false, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": false, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 63009, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "guncelleme_otomatik": false, "telefon_acik": false, "auto_accept_migrated": true}}} | {"status": 200, "json": {"ok": true, "settings": {"ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "video_quality": "best", "windows_notifications": false}}} |
| `crates/afudm-api/src/lib.rs:44` | `/settings` / wrong_types | {"status": 200, "json": {"ok": true, "settings": {"language": "auto", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\downloads", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": false, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": false, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": false, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": false, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 63009, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "guncelleme_otomatik": false, "telefon_acik": false, "auto_accept_migrated": true, "url": [], "gid": {}, "action": 3, "dest_dir": false}}} | {"status": 200, "json": {"ok": true, "settings": {"action": 3, "ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "dest_dir": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "gid": {}, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "url": [], "video_quality": "best", "windows_notifications": false}}} |
| `crates/afudm-api/src/lib.rs:44` | `/settings` / unicode | {"status": 200, "json": {"ok": true, "settings": {"language": "auto", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\downloads", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": false, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": false, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": false, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": false, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 63009, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "guncelleme_otomatik": false, "telefon_acik": false, "auto_accept_migrated": true, "url": "http://127.0.0.1:63005/İğdır/你好/😀", "gid": {}, "action": 3, "dest_dir": false, "filename": "İğdır_日本😀.bin"}}} | {"status": 200, "json": {"ok": true, "settings": {"action": 3, "ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "dest_dir": false, "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "filename": "İğdır_日本😀.bin", "gid": {}, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "url": "http://127.0.0.1:63005/İğdır/你好/😀", "video_quality": "best", "windows_notifications": false}}} |
| `crates/afudm-api/src/lib.rs:44` | `/settings` / traversal | {"status": 200, "json": {"ok": true, "settings": {"language": "auto", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\downloads", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": false, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": false, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": false, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": false, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 63009, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "guncelleme_otomatik": false, "telefon_acik": false, "auto_accept_migrated": true, "url": "http://127.0.0.1:63005/missing", "gid": {}, "action": 3, "dest_dir": "..\\escape_t2", "filename": "..\\escape_t2"}}} | {"status": 200, "json": {"ok": true, "settings": {"action": 3, "ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "dest_dir": "..\\escape_t2", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "filename": "..\\escape_t2", "gid": {}, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "url": "http://127.0.0.1:63005/missing", "video_quality": "best", "windows_notifications": false}}} |
| `crates/afudm-api/src/lib.rs:44` | `/settings` / file | {"status": 200, "json": {"ok": true, "settings": {"language": "auto", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\downloads", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": false, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": false, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": false, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": false, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 63009, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "guncelleme_otomatik": false, "telefon_acik": false, "auto_accept_migrated": true, "url": "file:///invalid-t2", "gid": {}, "action": 3, "dest_dir": "..\\escape_t2", "filename": "..\\escape_t2"}}} | {"status": 200, "json": {"ok": true, "settings": {"action": 3, "ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "dest_dir": "..\\escape_t2", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "filename": "..\\escape_t2", "gid": {}, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "url": "file:///invalid-t2", "video_quality": "best", "windows_notifications": false}}} |
| `crates/afudm-api/src/lib.rs:44` | `/settings` / javascript | {"status": 200, "json": {"ok": true, "settings": {"language": "auto", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\downloads", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": false, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": false, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": false, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": false, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 63009, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "guncelleme_otomatik": false, "telefon_acik": false, "auto_accept_migrated": true, "url": "javascript:alert(1)", "gid": {}, "action": 3, "dest_dir": "..\\escape_t2", "filename": "..\\escape_t2"}}} | {"status": 200, "json": {"ok": true, "settings": {"action": 3, "ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "dest_dir": "..\\escape_t2", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "filename": "..\\escape_t2", "gid": {}, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "url": "javascript:alert(1)", "video_quality": "best", "windows_notifications": false}}} |
| `crates/afudm-api/src/lib.rs:44` | `/settings` / wrong_origin | {"status": 200, "json": {"ok": true, "settings": {"language": "auto", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\py\\downloads", "max_concurrent": 5, "split": 64, "max_conn_per_server": 16, "max_speed_kb": 0, "hiz_profili": "normal", "snail_speed_kb": 100, "clipboard_watch": false, "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "notify_telegram": false, "windows_notifications": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "shutdown_when_done": false, "sleep_when_done": false, "seed_ratio": 1.0, "auto_update_trackers": false, "video_quality": "best", "api_listen_port": 6811, "api_port": 6811, "kaydetme_penceresi": false, "kategori_klasorleri": true, "tepsiye_kucult": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "eklenti_imzasiz_izin": true, "baslangicta_tepside": true, "ek_trackerlar": "", "canli_trackerlar": "", "tracker_tarama_zamani": 0, "tracker_tarama_ozeti": {}, "tracker_otomatik_tara": false, "lan_erisimi": false, "internet_paylasim": true, "ag_konumlari": "", "proxy": "", "system_proxy": false, "automation_enabled": false, "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "automation_checksum": true, "automation_extract": false, "automation_move_to": "", "automation_rename_to": "", "automation_script": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_port": 63009, "sunucu_istek_limiti": 120, "sunucu_hatali_limit": 8, "sunucu_kilit_saniye": 300, "sunucu_izinli_originler": "", "sunucu_istemci_kaydi": true, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "guncelleme_otomatik": false, "telefon_acik": false, "auto_accept_migrated": true, "url": "javascript:alert(1)", "gid": {}, "action": 3, "dest_dir": "..\\escape_t2", "filename": "..\\escape_t2"}}} | {"status": 200, "json": {"ok": true, "settings": {"action": 3, "ag_konumlari": "", "api_listen_port": 6811, "api_port": 6811, "auto_accept_migrated": true, "auto_update_trackers": false, "automation_checksum": true, "automation_enabled": false, "automation_extract": false, "automation_move_to": "", "automation_notify": true, "automation_power": "none", "automation_power_seconds": 60, "automation_rename_to": "", "automation_script": "", "automation_steps": ["checksum", "extract", "move", "rename", "script", "notify", "power"], "baslangicta_tepside": true, "canli_trackerlar": "", "clipboard_exts": "zip,rar,7z,exe,msi,iso,pdf,mp4,mkv,mp3,apk,dmg,torrent", "clipboard_watch": false, "dest_dir": "..\\escape_t2", "download_dir": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_vy3rcclm\\rs\\downloads", "ek_trackerlar": "", "eklenti_imzasiz_izin": true, "eklenti_max_boyut_mb": 200, "eklenti_max_oran": 100.0, "filename": "..\\escape_t2", "gid": {}, "guncelleme_otomatik": false, "hiz_profili": "normal", "internet_paylasim": true, "kategori_klasorleri": true, "kaydetme_penceresi": false, "lan_erisimi": false, "language": "auto", "max_concurrent": 5, "max_conn_per_server": 16, "max_speed_kb": 0, "notify_telegram": false, "proxy": "", "seed_ratio": 1.0, "shutdown_when_done": false, "sleep_when_done": false, "snail_speed_kb": 100, "split": 64, "sunucu_acik": false, "sunucu_adres": "yerel", "sunucu_hatali_limit": 8, "sunucu_istek_limiti": 120, "sunucu_istemci_kaydi": true, "sunucu_izinli_originler": "", "sunucu_kilit_saniye": 300, "sunucu_port": 63080, "sunucu_profil_id": 0, "sunucu_proxy_guven": false, "system_proxy": false, "telefon_acik": false, "telegram_bot_token": "[REDACTED]", "telegram_chat_id": "", "tepsiye_kucult": true, "tracker_otomatik_tara": false, "tracker_tarama_ozeti": {}, "tracker_tarama_zamani": 0, "url": "javascript:alert(1)", "video_quality": "best", "windows_notifications": false}}} |
| `crates/afudm-extras/src/h/mod.rs:80` | `/share_create` / broken_json | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek okunamadi. Yeniden dene.", "error": "Istek okunamadi. Yeniden dene."}} | {"status": 400, "json": {"code": "GOVDE_HATASI", "error": "Istek bicimi uygun degil. Yeniden dene.", "message": "Istek bicimi uygun degil. Yeniden dene.", "ok": false}} |
| `crates/afudm-extras/src/h/mod.rs:80` | `/share_create` / huge | {"status": 413, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "error": "Istek boyutu uygun degil. Daha kucuk bir istek gonder."}} | {"status": 413, "json": {"raw": "Failed to buffer the request body: length limit exceeded"}} |
| `app/src/windows_rota.rs:29` | `/windows-integration` / broken_json | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek okunamadi. Yeniden dene.", "error": "Istek okunamadi. Yeniden dene."}} | {"status": 400, "json": {"code": "BAD_REQUEST", "error": "gecersiz JSON govdesi", "message": "gecersiz JSON govdesi", "ok": false}} |
| `app/src/windows_rota.rs:29` | `/windows-integration` / huge | {"status": 413, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek boyutu uygun degil. Daha kucuk bir istek gonder.", "error": "Istek boyutu uygun degil. Daha kucuk bir istek gonder."}} | {"status": 413, "json": {"raw": "Failed to buffer the request body: length limit exceeded"}} |
| `app/src/windows_rota.rs:29` | `/windows-integration` / list | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 400, "json": {"code": "BAD_REQUEST", "error": "action apply, remove veya test olmali", "message": "action apply, remove veya test olmali", "ok": false}} |
| `app/src/windows_rota.rs:29` | `/windows-integration` / null | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 400, "json": {"code": "BAD_REQUEST", "error": "action apply, remove veya test olmali", "message": "action apply, remove veya test olmali", "ok": false}} |
| `app/src/windows_rota.rs:29` | `/windows-integration` / bool | {"status": 400, "json": {"ok": false, "code": "GOVDE_HATASI", "message": "Istek bicimi uygun degil. Yeniden dene.", "error": "Istek bicimi uygun degil. Yeniden dene."}} | {"status": 400, "json": {"code": "BAD_REQUEST", "error": "action apply, remove veya test olmali", "message": "action apply, remove veya test olmali", "ok": false}} |

HTTP durum 0 bir taşıma hatasıdır; tek başına PANIC veya süreç ölümü kanıtı değildir. Dev gövde reddedilirken Python bağlantıyı kesebilir. Bu yüzden tüm farklar kesin ürün hatası diye sınıflandırılmaz.

### 📍 Çökme sonrası devam — http / py

Konum: `crates/afudm-engine/src/args.rs:50` (Python karşılığı `P/core/daemon.py:148`). `--save-session-interval=0` otomatik session kaydını kapatır; `.aria2` için 60 saniye ayrı ayardır.

Yeniden üret: `python -B tests_hata/hepsi.py --only crash`; 192 MiB yerel indirme %40 civarında yalnız test PID ağacını zorla kapat, aynı veriyle yeniden başlat. Beklenen: aynı dosyanın kalan parçaları indirilir ve SHA-256 eşleşir. Gerçek:

```json
{
  "fraction": 0.41162109375,
  "control_exists": true,
  "session_bytes": 0,
  "integrity": "ok",
  "sha_ok": false,
  "range_after_restart": false,
  "taskkill_exit": 1
}
```

Session kaydı gözlemi tek başına kök nedeni kanıtlamaz; üretim yeniden kurma yolu ayrıca incelenmeli.

### 📍 Çökme sonrası devam — http / rs

Konum: `crates/afudm-engine/src/args.rs:50` (Python karşılığı `P/core/daemon.py:148`). `--save-session-interval=0` otomatik session kaydını kapatır; `.aria2` için 60 saniye ayrı ayardır.

Yeniden üret: `python -B tests_hata/hepsi.py --only crash`; 192 MiB yerel indirme %40 civarında yalnız test PID ağacını zorla kapat, aynı veriyle yeniden başlat. Beklenen: aynı dosyanın kalan parçaları indirilir ve SHA-256 eşleşir. Gerçek:

```json
{
  "fraction": 0.4043782552083333,
  "control_exists": true,
  "session_bytes": 0,
  "integrity": "ok",
  "sha_ok": false,
  "range_after_restart": false,
  "taskkill_exit": 1
}
```

Session kaydı gözlemi tek başına kök nedeni kanıtlamaz; üretim yeniden kurma yolu ayrıca incelenmeli.
