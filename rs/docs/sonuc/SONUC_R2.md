# R2 - Yerel 3.0.0 paket ve eski guncelleyici provasi

Durum: ISTENEN YEREL PROVA GECTI. 2026-10-18.

## Sonuc

- Gercek release ZIP: build_out/AfuDM-v3.0.0-win64.zip.
- Build, verify, yapi smoke ve gercek ZIP ile upgrade.py: EXIT 0.
- ZIP EXE ProductVersion=3.0.0, FileVersion=3.0.0.
- /_test/api_call, AFUDM_TEST_RPC_PORT, AFUDM_TEST_TOKEN dizgileri UTF-8/UTF-16LE olarak EXE icinde yok. Build --no-default-features kullandi.
- Eski guncelleyici gercek ZIP'i yerel sahte GitHub'dan indirdi, SHA-256 dogruladi, acti, gecici kurulumun EXE'sini degistirdi. Kurulan EXE hash'i ZIP icindekiyle ayni.
- data/keep.txt ve engine/user-extra.bin korundu. Kopya DB gocu de gecti.
- core/surum.py gecici 3.0.0 yapildi; finally icinde ozgun baytlariyla 2.9.9'a dondu. Son git farki bos.

## Degisen dosyalar

- rs/tests_hata/upgrade.py: gorevin acik izniyle listeye eklendi. --release-zip ve --output-dir destegi: 18 eklenen satir, 6 eski fallback satiri yalniz girintilendi; net +12. 20 satir siniri korundu. Parametresiz sentetik ZIP yolu korundu; bu provada kullanilmadi. Ayri rapor klasoru mevcut T2 raporlarini korudu.
- rs/docs/sonuc/SONUC_R2.md: bu rapor.
- build_out/: ZIP, staging/paket ve r2-evidence-20261018-131421/ ham kanitlari. Baslangicta build_out yoktu; dosya silinmedi.
- Build/verify/smoke betikleri hata vermedi, degistirilmedi. Baska ekiplerin mevcut degisikliklerine dokunulmadi.

## Yontem ve sinirlar

Guncelleyici kaynagi C:/Users/afuuu/Desktop/afuproject/AfuDM/core/guncelleme.py yalniz okundu/import edildi. Kaynak surumu 2.9.6; T2 yontemindeki gibi yalniz izole helper icinde SURUM=2.9.8 kullanildi. Izinli indirme oneki yalniz helper icinde loopback sunucusuna yoneltildi. Gercek kontrol/indirme/SHA/acma/hazir/uygulama kodu kullanildi. Gecici PowerShell scriptine yalniz yeniden acmayi yakalayan Start-Process fonksiyonu eklendi; asil kopyalama/yedekleme mantigi calisti.

Kullanicinin AfuDM kopyasina yazilmadi, orada test/derleme yapilmadi. DB yalniz fiziksel kopyalandi, SQLite gecici kopyaya baglandi. Pencere acilmadi. Uretim EXE'si calistirilmadi. Mevcut migration testi gecici test EXE'sini --t2-migrate-only ile gizli calistirdi. rs/tests_hata/bin/ dosyalarina yazilmadi; arka plan testi durdurulmadi. Korunan 6810/6811 portlarina baglanilmadi; sahte sunucu 127.0.0.1:58067 kullandi. Yasak git komutlari kullanilmadi.

Smoke YAPI dogrulamasidir; uretim UI/runtime testi veya temiz Windows/WebView2 ortami onayi degildir.

## Artifact - ZIP boyutu ve SHA-256

```json
{
  "zip": "build_out\\AfuDM-v3.0.0-win64.zip",
  "size_bytes": 8233745,
  "sha256": "ae80445a3509ba03db8e0967b09c2d018bcebb0375dba65b024609b9f0fb7cd9",
  "exe_sha256": "d031f5a75fa47f3d959647eb44312f6b112d3fbe1d2fb374be654390c6b25005",
  "test_gate_strings_absent_utf8_utf16le": {
    "/_test/api_call": true,
    "AFUDM_TEST_RPC_PORT": true,
    "AFUDM_TEST_TOKEN": true
  }
}
```

## Build

```text
COMMAND: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_release_rust.ps1 -Tag v3.0.0 -Offline
version gate: 3.0.0 ['3.0.0', '3.0.0', '3.0.0']
   Compiling afudm-app v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app)
   Compiling afudm-core v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-core)
   Compiling afudm-extras v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-extras)
    Finished `release` profile [optimized] target(s) in 2m 48s
Rust paket hazir: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\build_out\paket\AfuDM
Rust zip hazir: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\build_out\AfuDM-v3.0.0-win64.zip

EXIT: 0
```

## Verify

```text
COMMAND: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_release.ps1 C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\build_out\AfuDM-v3.0.0-win64.zip -PackageType Rust
verify OK: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\build_out\AfuDM-v3.0.0-win64.zip (7,9 MB), gerekli dosyalar mevcut
dosya sayisi: 16

EXIT: 0
```

## Smoke

```text
COMMAND: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke_test.ps1 C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\build_out\AfuDM-v3.0.0-win64.zip -PackageType Rust
verify OK: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\build_out\AfuDM-v3.0.0-win64.zip (7,9 MB), gerekli dosyalar mevcut
dosya sayisi: 16
smoke OK (yapi): C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\build_out\AfuDM-v3.0.0-win64.zip Rust paketi dogrulandi; EXE baslatilmadi

EXIT: 0
```

## Eski guncelleyici

```text
COMMAND: "C:\Program Files\Python311\python.exe" -B rs/tests_hata/upgrade.py --release-zip C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\build_out\AfuDM-v3.0.0-win64.zip --output-dir C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\build_out\r2-evidence-20261018-131421
MIGRATION GECTI
UPDATER GECTI

EXIT: 0
```

## ZIP EXE FileVersionInfo

```text
ZIP EXE ProductVersion=3.0.0; FileVersion=3.0.0
```

## Guncelleyici ham sonuc

```text
{
  "status": "GECTI",
  "api": {
    "control": {
      "ok": true,
      "var": true,
      "mevcut": "2.9.8",
      "yeni": "3.0.0",
      "notlar": "T2 local update",
      "zip_url": "http://127.0.0.1:58067/AfuDM-v3.0.0-win64.zip",
      "sha_url": "http://127.0.0.1:58067/AfuDM-v3.0.0-win64.zip.sha256"
    },
    "download": {
      "ok": true,
      "yol": "C:\\Users\\afuuu\\AppData\\Local\\Temp\\afudm_t2_update_e69g8075\\upgrade\\data\\guncelleme\\yeni\\AfuDM"
    },
    "ready": true,
    "apply": {
      "ok": true,
      "kapat": true
    },
    "launcher_pids": [
      36604
    ]
  },
  "helper_exit": 0,
  "helper_stderr": "",
  "exe_replaced_sha256": "d031f5a75fa47f3d959647eb44312f6b112d3fbe1d2fb374be654390c6b25005",
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

## Kopya DB gocu

```text
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
      "events": 10015,
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
    "history_sha256": "ef05e8cab3423208efca402687113353c576219d6953c6fb40519a8048dc3f96",
    "user_version": 10
  },
  "after": {
    "integrity": "ok",
    "counts": {
      "downloads": 119,
      "settings": 73,
      "events": 10015,
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
    "history_sha256": "ef05e8cab3423208efca402687113353c576219d6953c6fb40519a8048dc3f96",
    "user_version": 10
  },
  "exit_code": 0,
  "marker": true,
  "scope": "Real Rust SqliteStore open/migrations only; full Manager startup intentionally not used on copied user queue."
}
```

## Ek dogrulama - gercek cikti

ZIP EXE byte taramasi Python zipfile/hashlib; surum kontrolu PowerShell FileVersionInfo ile yapildi.

```text
ZIP EXE hash equals updater installed EXE hash; relaunch captured: OK
upgrade.py syntax: OK
upgrade.py LF only: True
ZIP EXE ProductVersion=3.0.0; FileVersion=3.0.0
VERSION RESTORED; original bytes identical: True
git diff --numstat -- rs/tests_hata/upgrade.py: 18 6 rs/tests_hata/upgrade.py
python -B scripts/surum_oku.py: 2.9.9
```

## git diff --stat -- core/surum.py

```text
[empty output]
EXIT: 0
```

## git diff --check -- core/surum.py rs/tests_hata/upgrade.py rs/docs/sonuc/SONUC_R2.md

```text
[empty output]
EXIT: 0
```

## git status --short

```text
 M .github/workflows/ci.yml
 M .github/workflows/quality-gate.yml
 M .github/workflows/release.yml
 M release-please-config.json
 M rs/app/src/boot.rs
 M rs/app/src/kopru_h.rs
 M rs/app/tauri.conf.json
 M rs/crates/afudm-core/src/queue.rs
 M rs/crates/afudm-core/src/queue/tests.rs
 M rs/crates/afudm-extras/src/g1/guncelleme.rs
 M rs/crates/afudm-extras/src/g1/reliability.rs
 M rs/crates/afudm-extras/src/h/paylasim.rs
 M rs/tests_hata/upgrade.py
 M scripts/smoke_test.ps1
 M scripts/verify_release.ps1
?? rs/docs/gorev/GOREV_FIX8_INCELEME.md
?? rs/docs/gorev/GOREV_R1_RELEASE_RUST.md
?? rs/docs/gorev/GOREV_R2_YEREL_PROVA.md
?? rs/docs/sonuc/SONUC_FIX8.md
?? rs/docs/sonuc/SONUC_R1.md
?? rs/docs/sonuc/SONUC_R2.md
?? scripts/build_release_rust.ps1
EXIT: 0
```
