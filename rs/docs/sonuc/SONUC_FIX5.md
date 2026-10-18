# SONUC FIX5 - aria2 senkronizasyonu ve /dosya

## Uygulanan degisiklikler

- ✅ `queue::sync_aria2`: Python `_sync_aria2` karsiligi. Aktif ve durmus islerin durum, boyut, dosya adi, hata ve bitis zamani DB'ye yazilir; magnet parent/child GID ve secim devri uygulanir. Tamamlanma kancalari yonetici kilidinin disinda, bir kez calisir.
- ✅ `queue/shaping.rs`: snapshot tamamlanma islemeyi ve DB'ye yeniden baglamayi yapmaz; tamamlanmis is purge sonrasi DB'den `start_after` dahil okunur.
- ✅ `queue/files.rs`, `queue.rs`: remove/save_session ve stop oncesinde senkronizasyon, sonra purge. Purge diger tamamlanmis islerin kaydini kaybettirmez.
- ✅ `app/src/izleme.rs`, `boot.rs`: bagimsiz 500 ms senkron dongusu, uyuyan motorda 5 sn. Video tamamlanmasi uyurken de islenir; dosya butunluk kontrolu motoru uyandirmaz. Ayri idle thread yerine senkronizasyondan sonra idle kontrolu yapilir; DB'deki bekleyen isler purge yarisini engeller.
- ✅ `afudm-api/transfer.rs`, `queue/files.rs`: `/dosya` once aria2 files listesindeki ilk dolu yol, sonra DB.path; kok disi dosyalar yine 403. Testte Python'un da 200 verdigi temizlenmemis yeni `phone.bin` indirilir; icerik kaynakla birebir karsilastirilir.
- ✅ `queue/tests.rs`: snapshot'in tamamlanmayi islememesi, purge oncesi DB senkronu, tek bildirim, hata kaydi, video tamamlanmasi ve uykuda RPC yapilmamasi regresyonlari.
- ✅ `tests_parity/uyum_testi.py`: sunucu port=0 ile atomik baglanir ve a.bin govdesi onceden dogrulanir. a.bin DB'ye ulasmadan purge yapan kontrol adimlari baslamaz. Torrent metadata sonrasi gercek child GID kullanilir. Iki tarafta ayni aria2/yt-dlp kopyalari ve ayri veri/motor klasorleri kullanilir. Kapanis kendi Popen sureclerini bekler; artan motorlar yalniz bu kosunun tam exe yoluyla kapatilir.

## Ortam sorununun nedeni

Tiny HTTP indirmesi aria2'de complete oldugu halde 500 ms arka plan dongusu henuz DB'ye yazmadan remove/save_session tum stopped sonuclarini purge edebiliyordu. Bu hem Python hem Rust'ta a.bin satirinin kaybolmasini acikliyor. Harness artik yalniz motor complete degil, salt okunur DB status=complete kosulunu da bekliyor; mevcut govde/SHA-256 kontrolleri korunuyor. Onceki turdan acik kalan test kopyalari tam `Temp/afudm_t1_*/rs_app` exe yoluyla temizlendi. Canli uygulama exe yollarina gore surec kapatilmadi.

Python wrapper `AFUDM_DATA_ROOT` ayarini import oncesi verir; `paths.DATA` icin gecici kok assertion'i vardir. Test 6810/6811'e istek gondermez. Python API/RPC ve dosya sunucusu bos portlarda; Rust RPC ayri secret ve veri klasorunde bos port arar. Gercek Python portu wrapper logunda yazilir.

## Sozlesme sorunu

`ApiCtx` RPC sunmuyor; ortak `ManagerApi` telefon yolu metodu icermiyor. Bu goreve kapali trait dosyalari degistirilmedi. Gecici cozum: `resolve_item_path` uzerinden gercek aria2 GID'si olamayacak NUL onekli `\0phone:` secicisi. Kalici onerimiz ortak trait'e `phone_download_path(gid)` eklenmesidir.

## Dogrulama

- `cargo test -p afudm-core -p afudm-api -p afudm-engine`: EXIT 0; API 10, core 103, engine 11 basarili; core 2 ignored.
- `cargo build -p afudm-core -p afudm-api -p afudm-engine`: EXIT 0.
- `cargo clippy -p afudm-core -p afudm-api -p afudm-engine -- -D warnings`: EXIT 0.
- Degisen Rust dosyalari `rustfmt --edition 2021 --config skip_children=true` ile bicimlendirildi; ayni dosyalarda --check temiz. Workspace genelindeki fmt kontrolu baska ekiplere ait onceden bicimlenmemis dosyalar nedeniyle temiz degil; bu dosyalara dokunulmadi.
- `git diff --check`: temiz. Harness Python syntax kontrolu: OK.

### Ard isik uyum kosusu 8

98 adim; {'kozmetik': 2, 'orta': 2}; kritik=0. Ham kanit: `fix5-parity-8.json`, `fix5-parity-8.log`.

- 4.3 / kozmetik / $.message: mesaj metni farkli
- 4.3 / orta / $.error: Python='canli degistirilemedi: aria2.changeOption: Cannot change option for GID#46b29ddd35d25f5c' Rust='canli degistirilemedi: aria2.changeOption: Cannot change option for GID#d222518b82938862'
- 7.5 / orta / $.error: Python='aria2.tellStatus: GID 881ca5097e4df2b4 is not found' Rust='aria2.tellStatus: GID 44ac987af00954d5 is not found'
- 8.11 / kozmetik / $.preview.events[0].message: mesaj metni farkli

### Ard isik uyum kosusu 9

98 adim; {'kozmetik': 2, 'orta': 2}; kritik=0. Ham kanit: `fix5-parity-9.json`, `fix5-parity-9.log`.

- 4.3 / kozmetik / $.message: mesaj metni farkli
- 4.3 / orta / $.error: Python='canli degistirilemedi: aria2.changeOption: Cannot change option for GID#47cd6e070f349d2a' Rust='canli degistirilemedi: aria2.changeOption: Cannot change option for GID#52bbaec126fdcdb4'
- 7.5 / orta / $.error: Python='aria2.tellStatus: GID d2cad2c3a7c0c0ad is not found' Rust='aria2.tellStatus: GID 4c9136e87a1e2209 is not found'
- 8.11 / kozmetik / $.preview.events[0].message: mesaj metni farkli

Orta farklar 4.3 ve 7.5 hata metinlerindeki her kosuda rastgele uretilen GID degerlerinden kaynaklanir. 4.3 kozmetik mesaj farki da ayni GID'dir. 8.11 diagnostics-preview olay mesaji metni farklidir; bu gorevin dosya sahipligi disindadir. Kritik farklari saklamak icin normalizasyon eklenmedi.

## Sinirlar ve veri guvenligi

P/data once/sonra dosya imzasi bazi kosularda degisti (`afudm.db` / `afudm.db-wal`). Canli uygulamalar acikken bu tek basina testin yazdigi veya yazmadigi kaniti degildir. Test kendi veri kokunu assertion ile dogrular ve kaynak Python dosyalarini degistirmez; **canli P/data degismedi iddiasi yapilmiyor**. Canli uygulamalar kapatilmadi. Test sureclerinin son kontrolu ve release sonucu asagida kaydedilir.

Commit, push veya yikici git komutu calistirilmadi. Bu gorevde eklenen bos `todo!()` govdesi yok.


## Son durum

Tamamlandi: iki ard isik kosuda kritik=0 (98'er adim), 124 test basarili, 2 ignored; crate build/clippy EXIT 0. Release derleme EXIT 0 (2m 51s); app clippy EXIT 0. Test exe ve motorlari kapanis sonrasi surec listesinde yok. Canli AfuDM surecleri yerinde birakildi.

## Gercek komut ciktilari (son 30 satir)

### fix5-tests.log

```text
test tests::secrets_and_session_credentials_survive_migration_safely ... ok
test engines::tests::download_checksum_failure_and_invalid_binary_preserve_existing_engine ... ok
test tests::rpc_default_status_keys_match_python_for_each_poll ... ok
test tests::rpc_all_trait_methods_send_python_methods_and_parameters ... ok
test tests::daemon_arguments_and_listener_detection_match_python ... ok
test engines::tests::sha256_successfully_verified_before_installing_direct_binary ... ok
test engines::tests::download_extracts_only_named_zip_member_and_validates_executable ... ok
test tests::rpc_rejects_bad_http_json_and_rpc_shapes_without_panics_or_secrets ... ok
test tests::real_aria2_random_port_ownership_idle_and_http_download ... ok

test result: ok. 11 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 20.14s

   Doc-tests afudm_api

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests afudm_core

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests afudm_engine

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

```

### fix5-build.log

```text
cargo :     Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.33s
At line:2 char:1
+ cargo build -p afudm-core -p afudm-api -p afudm-engine *> docs/sonuc/ ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (    Finished `d...get(s) in 0.33s:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError

```

### fix5-clippy.log

```text
cargo :     Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.44s
At line:2 char:196
+ ... $testCode"; cargo clippy -p afudm-core -p afudm-api -p afudm-engine - ...
+                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (    Finished `d...get(s) in 0.44s:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError

```

### fix5-release.log

```text
cargo :    Compiling afudm-app v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app)
At line:2 char:127
+ ... TEXITCODE"; cargo build --release --manifest-path app/Cargo.toml *> d ...
+                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (   Compiling af...fuDM_rs\rs\app):String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError

    Finished `release` profile [optimized] target(s) in 2m 51s
```

### fix5-app-clippy.log

```text
cargo :    Compiling afudm-app v3.0.0 (C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\app)
At line:2 char:304
+ ... og -Tail 3; cargo clippy --manifest-path app/Cargo.toml -- -D warning ...
+                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (   Compiling af...fuDM_rs\rs\app):String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError

    Finished `dev` profile [unoptimized + debuginfo] target(s) in 1.73s
```

### fix5-parity-8.log

```text
[8.7] POST /eklenti incele: py=200 rs=200 fark=0
[8.8] POST /eklenti bilinmeyen eylem: py=400 rs=400 fark=0
[8.9] POST /linkgrabber metin yok (UI yolu atland�): py=400 rs=400 fark=0
[8.10] POST /reliability/integrity: py=200 rs=200 fark=0
[8.11] POST /reliability/diagnostics-preview: py=200 rs=200 fark=1
[8.12] GET /windows-integration (durum): py=200 rs=200 fark=0
[8.13] GET /_listener/ready (UI child degil): py=404 rs=404 fark=0
[8.14] GET /_listener/idle (UI child degil): py=404 rs=404 fark=0
[8.15] GET /_listener/status: py=404 rs=404 fark=0
[9.1] POST /share_create: py=200 rs=200 fark=0
[9.2] GET /s/<kod> (govde = a.bin birebir): py=200 rs=200 fark=0
[9.3] GET /s/<kod> Range (ilk 100 bayt): py=206 rs=206 fark=0
[9.4] GET /s/yanl�� kod: py=404 rs=404 fark=0
[9.5] GET /pair (e�le�me kapal�): py=403 rs=403 fark=0
[9.6] GET /m (mobil sayfa): py=200 rs=200 fark=0
[9.7] GET /manifest.webmanifest: py=200 rs=200 fark=0
[9.8] GET /i18n.js: py=200 rs=200 fark=0
[9.9] GET /sw.js: py=200 rs=200 fark=0
[9.10] GET /ikon.png: py=200 rs=200 fark=0
[9.11] POST /share_create gid yok: py=400 rs=400 fark=0
[10.1] POST /add_blob filename=blob.pdf: py=200 rs=200 fark=0
[10.2] POST /add_blob yol ay�r�c� (reddedilir): py=400 rs=400 fark=0
[10.3] POST /handoff/error: py=200 rs=200 fark=0
[10.4] POST /handoff/error hatal� g�vde: py=200 rs=200 fark=0
[10.5] POST /token/rotate: py=200 rs=200 fark=0
[10.6] GET /capabilities eski token (401): py=401 rs=401 fark=0
OZET: adim=98 kritik=0 orta=2 kozmetik=2
Rapor: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\tests_parity\rapor\sonuc_son.json
P\data degismedi: False
P\data imzasi degisen dosyalar: ['data\\afudm.db', 'data\\afudm.db-wal']
```

### fix5-parity-9.log

```text
[8.7] POST /eklenti incele: py=200 rs=200 fark=0
[8.8] POST /eklenti bilinmeyen eylem: py=400 rs=400 fark=0
[8.9] POST /linkgrabber metin yok (UI yolu atland�): py=400 rs=400 fark=0
[8.10] POST /reliability/integrity: py=200 rs=200 fark=0
[8.11] POST /reliability/diagnostics-preview: py=200 rs=200 fark=1
[8.12] GET /windows-integration (durum): py=200 rs=200 fark=0
[8.13] GET /_listener/ready (UI child degil): py=404 rs=404 fark=0
[8.14] GET /_listener/idle (UI child degil): py=404 rs=404 fark=0
[8.15] GET /_listener/status: py=404 rs=404 fark=0
[9.1] POST /share_create: py=200 rs=200 fark=0
[9.2] GET /s/<kod> (govde = a.bin birebir): py=200 rs=200 fark=0
[9.3] GET /s/<kod> Range (ilk 100 bayt): py=206 rs=206 fark=0
[9.4] GET /s/yanl�� kod: py=404 rs=404 fark=0
[9.5] GET /pair (e�le�me kapal�): py=403 rs=403 fark=0
[9.6] GET /m (mobil sayfa): py=200 rs=200 fark=0
[9.7] GET /manifest.webmanifest: py=200 rs=200 fark=0
[9.8] GET /i18n.js: py=200 rs=200 fark=0
[9.9] GET /sw.js: py=200 rs=200 fark=0
[9.10] GET /ikon.png: py=200 rs=200 fark=0
[9.11] POST /share_create gid yok: py=400 rs=400 fark=0
[10.1] POST /add_blob filename=blob.pdf: py=200 rs=200 fark=0
[10.2] POST /add_blob yol ay�r�c� (reddedilir): py=400 rs=400 fark=0
[10.3] POST /handoff/error: py=200 rs=200 fark=0
[10.4] POST /handoff/error hatal� g�vde: py=200 rs=200 fark=0
[10.5] POST /token/rotate: py=200 rs=200 fark=0
[10.6] GET /capabilities eski token (401): py=401 rs=401 fark=0
OZET: adim=98 kritik=0 orta=2 kozmetik=2
Rapor: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\tests_parity\rapor\sonuc_son.json
P\data degismedi: False
P\data imzasi degisen dosyalar: ['data\\afudm.db-wal']
```
