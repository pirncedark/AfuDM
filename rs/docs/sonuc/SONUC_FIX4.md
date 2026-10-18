# SONUC FIX4: HTTP indirme doğruluğu ve snapshot (Entegrasyon-4)

Durum: **KISMI, hedef (kritik = 0) TAMAMLANMADI.** Son koşu ortam nedeniyle sonuç vermedi (aşağıda). Bu dosya yalnız kanıtlanan şeyleri yazar.

## Yazılan dosyalar

- `crates\afudm-core\src\queue\files.rs`: değişiklik yapıldı, sonra geri alındı (aşağıda). Son hâl Python ile aynı (ek değişiklik yok).
- `crates\afudm-core\src\queue.rs` (`change_option` hata metni): değişti. Python `canli degistirilemedi: %s` (`str(exc)[:160]`) biçimi uygulandı.
- `docs\sonuc\SONUC_FIX4.md`: bu dosya.

## Hata arama (ikiye bölme) ve kanıtlar

1. **Sorun 1 (5.3d a.bin içeriği):** aria2 başlatma argümanları Python (`core\daemon.py` 105-135) ile Rust (`crates\afudm-engine\src\args.rs`) birebir aynı. `addUri` seçenekleri (`dir`, `out`, `header`, `max-connection-per-server`, `min-split-size`) Python `manager.py` 688-710 ile Rust `queue.rs` 500-520 eşdeğer. Üç koşuda da `5.3d` disk SHA-256 iki tarafta **eşit** (`sha_ok: true`, `aday_sayisi: 1`). Eski raporda görülen fark bu build'de **tekrarlanmadı**; kök neden kodda bulunmadı, ama bu bir kanıt eksikliği değil, eski exe'nin farkıydı.
2. **Sorun 2 (5.x / 9.x `/snapshot`, `/indir`, `/share_create`):**
   - `5.1` (her iki taraf `complete`) ve `5.3` (`/indir` 200, gövde = kaynak), `9.2`-`9.3` (`/s/<kod>` 200/206, gövde = kaynak) ilk iki koşuda **geçti** (fark 0).
   - Kalan kritik `5.2`: `$.items[0].start_after` Rust'ta yok. Sebep kanıtlandı: Python tamamlanmış indirmeyi aria2 `tellStopped` listesinde DEĞİL, DB satırından (`_shape_row`, `start_after` içerir) gösteriyor. Python bunu `remove()` içindeki `daemon.save_session()` → `aria2.purgeDownloadResult` ile sağlıyor (`core\manager.py` 886-990, `core\daemon.py` 258-263). Rust `files.rs` `remove` yalnız `rpc().save_session()` (purge yok) çağırıyor, bu yüzden tamamlanmış gid aria2'de kalıyor ve aria şekliyle dönüyor.
   - Denendi: `files.rs` içinde `aria2.purgeDownloadResult` çağrısı eklendi. **Sonuç kötüleşti** (kritik 3 → 22): Rust tamamlanmayı yalnız snapshot yoklamasında işlediği için (`queue\shaping.rs` `known_complete`), purge tamamlanmayı işlenmeden sildi; 5.1 `satir_yok`. **Geri alındı** (kendi eklediğim satır kaldırıldı; `git restore` kullanılmadı).
   - Kök neden (kesin değil, ama doğrulanmalı): Rust'ta tamamlanma olayının snapshot'tan bağımsız işlenmesi gerekiyor (Python `_sync_aria2` eşdeğeri). Bu, `afudm-core` dışında da bir değişiklik gerektirebilir; ayrı bir görev olarak ele alınmalı.
3. **Sorun 3 (`/control resume`, 4.2):** Python `manager.resume` içinde `self.rpc.unpause(gid)` çağrısı hatayı yakalamıyor → `INTERNAL` 500. Rust şu an aynı 500 gövdesini döndürüyor (`queue.rs` `resume`, `m.rpc().unpause(gid)?`). **fark 0**. 📍 Python'un 500'ü bir **Python hatası** (bilinen gid için unpause beklenen hata; kontrat 400/502 olmalıydı). Rust Python'u taklit ediyor; kararı kullanıcıya bırakıyorum.
   - Önceki turdaki "Rust 200" durumu bu build'de yok (kod değişmiş).

## Yapılan değişiklik (kalıcı)

- `queue.rs` `change_option` hata metni: `canli degistirilemedi: <aria2 hatası ilk 160 karakter>` (Python ile aynı biçim). Test: 4.3 orta farkı artık yalnız GID değerinde (`GID#e041...` / `GID#c77e...`). Metin birebir aynı; harness değer karşılaştırması GID'i gerçek fark sayıyor, bu bir harness/koşu artefaktı.

## Sınıflandırılmış kalan fark (son geçerli koşuya göre, ilk koşu: kritik 3)

| Adım | Sınıf | Durum | Sorumlu / neden |
|---|---|---|---|
| 5.2 `start_after` | kritik | Rust tamamlanmayı aria2'den gösteriyor | `afudm-core` tamamlanma olayı (yukarıda), ayrı görev |
| 5.6 `/dosya ?k=` | kritik (her iki taraf) | Python 404: aria2 gid yok + DB `path` kolonu yok → `kayit.get("path")` boş. Rust `transfer.rs` `phone_download` yalnız DB `path` okuyor (aria2 `tellStatus.files` adımı yok) | **📍 `crates\afudm-api\src\transfer.rs` `phone_download`**: bu dosya bu görevin kapsamı dışında (api yalnız 3. madde). Python'un ilk adımı (aria2 `files[0].path`) eklenmeli; Python'un kendi davranışı da bu |
| 4.3 orta | — | yalnız GID değeri | harness artefaktı |
| 8.11 kozmetik | kozmetik | mesaj metni | Python `diagnostics-preview` mesajı; Rust ayrı mesaj |
| 7.3 `/renew` (orta, son koşuda) | orta | iki taraf 400 metin farkı | yeni karşılaştırılmadı, Rust metni Python'a uydurulabilir |

## Test ve doğrulama

- `cargo test -p afudm-core`: **98 passed, 0 failed, 2 ignored** (EXIT 0).
- `cargo clippy -p afudm-core -- -D warnings`: **temiz** (EXIT 0).
- `cargo build --release --manifest-path app\Cargo.toml`: **EXIT 0** (son derleme, purge geri alındıktan sonra).
- `cargo test -p afudm-core` son turda geri alım sonrası koşulmadı (değişiklik yalnız bir satır silme). `afudm-api` / `afudm-engine` testleri çalıştırılmadı.

## Uyum testi (`python tests_parity\uyum_testi.py`)

| Koşu | Durum | Kritik | Orta | Kozmetik | Not |
|---|---|---|---|---|---|
| 1 (purge yok, 4.3 öncesi) | geçerli | 3 | 9 | 2 | 5.2 start_after; 5.6 iki taraf |
| 2 (purge eklenmiş) | kötü | 22 | 21 | 4 | satir_yok, purge yarışı; geri alındı |
| 3 (purge geri alınmış, 4.3 değişikliğiyle) | **geçersiz** | 10 | 2 | 3 | **ortam**: iki tarafta da 5.1 `satir_yok` (3.1 gid üretildi, 150 sn snapshot'ta satır yok). Kod farkı değil; yeniden koşulmalı |

Son çıkış kodu: 1 (kritik var). Ham rapor: `tests_parity\rapor\sonuc_son.json` (son koşu, geçersiz).

## Açık sorular / sonraki adım

1. `tests_parity\uyum_testi.py` ortam sorununu (3. koşu: iki tarafta indirme tamamlanmadı) doğrula: yerel dosya sunucusu (`{fs}`), `127.0.0.1` IP sınırı ve 6810 aria2 ile çakışma yok mu. Kullanıcının 6811 AfuDM ve 6810 aria2'si (PID 5932, 29328, 34488, 15004) dokunulmadan bırakıldı.
2. Rust tamamlanma olayının snapshot'tan bağımsız işlenmesi (Python `_sync_aria2`) → 5.2 kritiği.
3. `afudm-api` `phone_download` aria2 adımı → 5.6 kritiği (📍 transfer.rs).
4. Python `resume` 500'ü Python hatası: Python'u düzeltme kararı kullanıcıda.
5. Kullanıcının 6811 AfuDM ve `P\data` klasörüne dokunulmadı; test pencere açmadı; Notam'a yazılmadı.
6. `git` hiçbir yıkıcı komutla çalıştırılmadı; commit atılmadı.
