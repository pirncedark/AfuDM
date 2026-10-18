# SONUC_FIX1 — Entegrasyon-1 (A/B/C/E toparlama)

## Madde durumu
1. ✅ engine tests.rs: tellStatus satiri `json!` ile duzeltildi; getGlobalStat/getGlobalOption `{}` → `json!({})`; tellActive/tellWaiting/tellStopped/getPeers/getFiles/getServers `[]` → `json!([])` (tip cikarimi hatasi). Ek: serve_bytes harness'inde kabul edilen soket `set_nonblocking(false)` (Windows miras sorunu; testler kararsizdi).
2. ✅ api erisim.rs: `HizSinirlayici::ayarla(&mut self, limit, hatali_limit, kilit_saniye)` eklendi (Python ayarla ile ayni alt sinirlar: limit/hatali >=1, kilit >=5).
3. ✅ SOZLESME: `torrent_dosyalari` → `Result<Json>` `{"dosyalar","hazir_degil","neden","gid"}`. torrent.rs imzasi + iki hazir_degil donusu (neden: "Magnet ustverisi henuz gelmedi; dosya listesi hazir degil."; gid = takip eden child gid) + son donus. api lib.rs /torrent/dosyalar dogrudan `result(...)`; tests.rs FakeManager guncellendi.
4. ✅ Tek kaynak: torrent.rs `State` icindeki preview/removed kopyalari kaldirildi (`State {}` bos). `durum_kilidi` → `queue_kilidi` (m.queue_state). Not: lib.rs (Claude) `torrent_state` alanini hala tutuyor; istenirse Claude kaldirabilir.
5. ✅ queue/proxy.rs (pub mod): parcala, aria2_secenekleri, url, sistem_proxysi (winreg, yalniz Windows), sistem_adresi, proksi_bul (= Python _proksi: is-acik → sistem(system_proxy acikken) → genel). queue.rs ekleme yolu ve torrent.rs iki TODO(proxy) noktasi buna baglandi. Eski settings.rs `proxy_options` / `system_proxy` (SOCKS'u reddeden ayri kopya) kaldirildi. ⚠ `komut_secenekleri` tasinmadi: Python'da hicbir yerde cagrilmiyor.
6. ✅ files.rs erase: `#[allow(clippy::permissions_set_readonly_false)]` (Windows salt-okunur bayragi icin zorunlu). Ek: afudm-db kaydet.rs needless_return duzeltildi (afudm-db benim sahipligim).
7. ✅ Testler ve clippy (`-D warnings`) yesil — asagida gercek cikti.
8. ✅ Bu dosya + SONUC_A/B/C/E eklemeleri.
9. ✅ `serve` (lib.rs:75) zaten `into_make_service_with_connect_info::<SocketAddr>()` kullaniyor; `/pair` rotasi Ekip H'de (afudm-extras/src/h/mod.rs) ve ConnectInfo bekliyor. Test eklendi: `serve_passes_client_addr_as_connect_info` (gercek TCP istegi, 200 + 127.0.0.1). Python'da IP'ye dayali yerel/uzak ayrimi: `security.rs` icindeki rate-limit anahtari ve `/pair` (loopback kontrolu) — ayni bilgi kullaniliyor.

## Yazilan / degisen dosyalar
- crates/afudm-engine/src/tests.rs
- crates/afudm-api/src/{erisim.rs, lib.rs, tests.rs, security.rs}
- crates/afudm-core/src/{torrent.rs, queue.rs, queue/settings.rs, queue/files.rs, queue/proxy.rs (yeni)}, crates/afudm-core/Cargo.toml (winreg, cfg(windows))
- crates/afudm-db/src/kaydet.rs (clippy)

## Sozlesme / sorunlar (Claude'a)
- afudm-core/Cargo.toml'da `afudm-db.workspace = true` satiri benim eklemem degil; calisma sirasinda belirdi. Kullanimi gorunmuyor — Claude/sahibi kontrol etsin.
- lib.rs `torrent_state` alani hala var (bos State).

## Test ve clippy (gercek cikti)
```
##### cargo test -p afudm-engine
test result: ok. 11 passed; 0 failed
##### cargo clippy -p afudm-engine --all-targets -- -D warnings
    Finished `dev` profile
##### cargo test -p afudm-db
test result: ok. 14 passed; 0 failed
##### cargo clippy -p afudm-db --all-targets -- -D warnings
    Finished `dev` profile
##### cargo test -p afudm-api
test result: ok. 9 passed; 0 failed
##### cargo clippy -p afudm-api --all-targets -- -D warnings
    Finished `dev` profile
##### cargo test -p afudm-core
test result: ok. 76 passed; 0 failed; 2 ignored
##### cargo clippy -p afudm-core --all-targets -- -D warnings
    Finished `dev` profile
```
Not: engine testleri ~20 sn suruyor (serve_bytes accept bekleme suresi); kararlilik icin iki kez kosuldu, ikisi de yesil.

## Bilinen
- Biçim: yeni dosya proxy.rs rustfmt'lendi; mevcut dosyalarin tamami `rustfmt --check` ile farkli (CRLF/eski biçim) — toplu fmt yapilmadi (cerrahi degisiklik ilkesi).
- Satir sonu: calisma agacindaki dosyalar CRLF; EKIP_KURALLARI LF diyor — dosyalar yeniden yazilmadi.
