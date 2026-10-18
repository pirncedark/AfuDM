# SONUC FIX6b — HTTP gövde farkları, çökme sonrası devam, boşta CPU

Ajan: Entegrasyon-6b (Codex kotası dolu, Claude yürüttü). Kapsam: crates\ ve tests_hata\ (app\src\ dokunulmadı; izleme.rs değişikliğini 6a/koordinatör yaptı).

## Durum özeti

| Madde | Durum |
|---|---|
| 1. Şekil bazlı karşılaştırma | Yapıldı |
| 2. Python gövde hataları (g2 rotaları) | Yapıldı; dev gövde Rust 413 davranışı korundu |
| 3. Çökme sonrası devam (Rust açılış kurtarması) | Yapıldı; `crash` Rust http+torrent 3/3 GEÇTİ |
| 4. cargo test + clippy | Yeşil (core, extras, api) |
| Ek 5. Boşta CPU | Hedef tutuldu: rs %0.125, py %0.166 (idle 300 sn) |
| Ek: butunluk_hepsini_tara (Python birebir) | Yapıldı; Python hatası aynen üretiliyor |
| Ek: reliability_recovery_preview [gecerli] | Yapıldı; `bridge` GECTI |

## Çökme sonrası devam — kök neden (güncel)

İlk raporda HTTP SHA hatasını `--disk-cache=64M` + `--auto-save-interval=60` ile ilişkilendirmiştim. Ölçümle bu REDDEDİLDİ:

- Kill anında diskteki veri, indirmenin tamamlandığı bildirilen kısımda %100 doğru. Tarama (`pre_restart_scan`): rs HTTP 0 bozuk parça, rs torrent 0 bozuk parça. Yani yazılmamış önbellek bloğu kaybı yok.
- İlk koşuda `resume deadline` 75 sn idi. Test sunucusu indirmeyi yavaşlatıyor; yeniden başlatma sonrası indirme 75 sn'de bitmedi. SHA, yarım dosyada hesaplanıyordu. Sıfır blokların başladığı yer (~120 MB), deadline anındaki ilerlemeyle örtüşüyor.
- `resume deadline` 300 sn yapılınca rs HTTP SHA tuttu, sıfır blok yok.

Sonuç: motor argümanı değişikliği GEREKMEDİ. `disk-cache` ve `auto-save-interval` deneyleri (3 varyant) bu kök neden kanıtlandığı için çalıştırılmadı; istenirse yapılabilir.

Test değişiklikleri (`tests_hata\scenarios.py`):
- `scan_dosya`: kill öncesi (`pre_restart_scan`) ve sonrası (`post_scan`) 64 KiB parça taraması (bozuk/sıfır sayısı, ilk bozuk ofset).
- Yeniden başlatma bekleme süresi 75 → 300 sn; torrent bekleme 160 → 300 sn (torrent %40'a yavaş ulaşıyor).

Test kapısı (`tests_hata\hepsi.py`): crash sonucu yalnız `rs` satırlarına bakar. Python'da açılış kurtarması yok; py satırları KALDI kalır ve referans olarak raporlanır.

## Crash sonuçları (motor args değişmedi: disk-cache 64M, auto-save 60)

| Koşu | rs http | rs torrent | py http | py torrent |
|---|---|---|---|---|
| 1 (deadline 300) | GECTI (sha, 0 sıfır blok) | GECTI (sha, 0 sıfır blok) | KALDI (devam yok) | KALDI |
| 2 (`rep1`) | GECTI | GECTI | KALDI | KALDI |
| 3 (`rep2`) | GECTI | GECTI | KALDI | KALDI |

`rep1`/`rep2`: `RESULT crash GECTI`. Kanıt dosyaları: scratchpad `crash_rep1.json`, `crash_rep2.json`.

Gözlem (Python, bilgi amaçlı): py torrent kill anında 6 sıfır parça (ofset 81788928) raporladı; yani aria2'nin ilerleme sayacı diskten önde olabiliyor. Rust kill anlarında bu görülmedi. Python'da bu ayrıca incelenebilir.

## Hız ölçümü (`--only resources`, idle 300 sn)

| Faz | py CPU % | rs CPU % | py MiB | rs MiB |
|---|---|---|---|---|
| idle | 0.166 | 0.125 | 44.7 | 72.3 |
| 1GiB | 4.222 | 3.295 | 56.2 | 74.9 |
| 3_concurrent | 2.519 | 2.184 | 55.5 | 75.9 |

Boşta CPU hedefi karşılandı (rs ≤ py). Önceki ölçüm (rs 1.04) izleme düzeltmesi öncesiydi.

## Yazılan dosyalar

- `crates\afudm-core\src\queue.rs`: `kesilenleri_kurtar` (açılış kurtarması), `sync_aria2` içinde motor uyanıkken bir kez; `State.kurtarma_bitti`.
- `crates\afudm-core\src\queue\tests.rs`: `acilis_kurtarmasi_aria2da_olmayan_bitmemis_kaydi_yeniden_ekler`.
- `crates\afudm-core\src\butunluk.rs`: `butunluk_hepsini_tara` Python ile aynı hatayı üretir; test `butunluk_hepsini_tara_python_gibi_hata_verir`.
- `crates\afudm-extras\src\g2\mod.rs`: `govde()` Python `_govde_oku` kurallarına göre; `GOVDE_HATASI`; birim testi `govde_tests`.
- `tests_hata\scenarios.py`: `fuzz_sig`, `hazirla_indirme`, `scan_dosya`, bekleme süreleri.
- `tests_hata\hepsi.py`: crash kapısı yalnız rs.
- `tests_hata\bin\AfuDM_test.exe`: güncel derleme.

## Test ve clippy

- `cargo test -p afudm-core -p afudm-extras -p afudm-api`: tümü geçti (core 104, extras 87, api 10).
- `cargo clippy -p afudm-core -p afudm-extras -p afudm-api --all-targets -- -D warnings`: temiz.
- `--only bridge`: GECTI. `--only resources`: GECTI.

## 📍 Python düzeltme önerileri (P = C:\Users\afuuu\Desktop\afuproject\AfuDM, değiştirilmedi)

1. `core\manager.py:2616` `self.store.all_downloads()` yok (`core\db.py` Store'da tanımlı değil) → `butunluk_hepsini_tara` her çağrıda AttributeError. Rust birebir aynı hatayı üretiyor. Öneri: `self.store.list(None, 1000000)` + `status == "complete"` ve `kind in ("http","ftp")` filtresi. Karar kullanıcıda; Rust da buna göre değişir.
2. `core\daemon.py:148` `--save-session-interval=0` ile Python açılışta bitmemiş indirmeleri yeniden eklemiyor → çökme sonrası devam yok. Öneri: Rust'taki `kesilenleri_kurtar` (queue.rs) mantığını Python'a taşımak: açılışta DB'deki `active/waiting/paused` http/torrent satırlarından aria2'de gid'i olmayanları aynı dir/out/seçenekle yeniden ekle; duraklatılmışları duraklat.
3. 2.9.x için aynı öneri geçerli (1 ve 2).

## Açık noktalar

- Çerezler yalnız bellekte (`state.cookies`); çerezli ve oturumda olmayan kayıtlar kurtarmada çerezsiz eklenir ve 401/403 ile hataya düşer. `auth_required` gid'ler "Yenile" ile başlatılır.
- Bu ortamda test sunucusu hızı ~1 MB/s; üretimde sonuçlar farklı olabilir. Deadline (300 sn) ayarı test sunucusuna göre seçildi.
