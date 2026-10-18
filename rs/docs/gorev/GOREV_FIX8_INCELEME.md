# FIX8: Claude gözden geçirme bulguları (codex)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM
Paralelde başka bir codex release.yml / scripts\ üzerinde çalışıyor: o dosyalara DOKUNMA.
YIKICI GIT YASAK: restore / checkout -- / reset / clean / stash / rebase / amend / push / switch / commit.
Kullanıcının AfuDM'ine (6810/6811), P\data ve AfuDM.exe'ye DOKUNMA. Pencere açma.

## ÇALIŞACAĞIN DOSYALAR (yalnız bunlar)
- app\src\boot.rs
- app\src\kopru_h.rs
- crates\afudm-extras\src\h\paylasim.rs
- crates\afudm-core\src\queue.rs (+ ilgili test dosyası crates\afudm-core\src\queue\tests.rs)
- crates\afudm-extras\src\g1\reliability.rs
- crates\afudm-extras\src\g1\guncelleme.rs
- docs\sonuc\SONUC_FIX8.md
Başka dosya gerekiyorsa dur ve SONUC'ta sor. Her düzeltmeye birim testi ekle (kırmızı → yeşil).

## Düzeltmeler
1. 📍 app\src\boot.rs:45-52 `bekleyen_geri_yuklemeyi_uygula`: `fs::rename(bekleyen, db_path)` öncesinde canlı DB'nin `-wal` ve `-shm` dosyaları silinmeli. Çökmeden kalan eski WAL, geri yüklenen DB'nin üstüne uygulanmasın. Python, bağlantıyı kapatıp (WAL checkpoint) taşıyor: P\core\reliability.py:126-137.
2. 📍 İki ayrı paylaşım kayıt defteri var:
   - app\src\kopru_h.rs:31 `PAYLASIMLAR` (UI share_create / list / delete, satır 632, 679, 727-740)
   - crates\afudm-extras\src\h\paylasim.rs:24 `PAYLASIMLAR` (HTTP/telefon /share_create, paylasim_ekle / bul / sil)
   Python'da tek defter var (P\app.py:1438-1473 `_Handler.shared_files`). Telefondan açılan paylaşım UI listesinde görünmüyor, silinemiyor. Son UI paylaşımı silinince tünel duruyor ve telefon linkleri sessizce ölüyor (kopru_h.rs:740).
   Tek defter yap (paylasim.rs'deki defter esas olsun; created zamanı da orada tutulsun). share_list / share_delete / tünel durdurma kontrolü bu defteri kullansın. Python share_list çıktı biçimini koru.
3. 📍 crates\afudm-core\src\queue.rs:512-517: istemciden gelen `filename`, temizlenmeden aria2 `out` olarak geçiyor. `..\..\Startup\x.exe` gibi bir değer dosyayı indirme kökü dışına yazabilir.
   `out`, tek bir dosya adı bileşenine indirgensin: `/ \ :` ve NUL, `.` ve `..` reddedilsin ya da güvenli ada çevrilsin. Mevcut temizleyici varsa onu kullan (ör. probe.rs `guvenli_dosya_adi`; `grep -rn "fn guvenli_dosya_adi" crates`).
   Python'da da aynı açık var (P\core\manager.py:695). Python'a dokunma; SONUC'ta 📍 ile 2.9.x düzeltme önerisi yaz.
4. 📍 crates\afudm-extras\src\g1\reliability.rs:155-159: `read_to_end` sınırsız.
   - Zip girdisinin boyutu (`girdi.size()`) makul bir üst sınırı (ör. 2 GiB) aşarsa reddet.
   - io::copy ile doğrudan dosyaya yaz, belleğe alma.
   - integrity_check'ten sonra `PRAGMA user_version` değeri, Rust'ın bildiği en yüksek şema sürümünden büyükse "yedek daha yeni bir sürümden" hatasıyla reddet. Şema sürümü sabiti crates\afudm-db içinde; `grep -rn "user_version" crates\afudm-db`.
5. 📍 crates\afudm-extras\src\g1\guncelleme.rs:240-245 `ajan()`: `timeout_recv_body` (ya da toplam `timeout_global`) yok. İndirme takılırsa güncelleme kilidi süresiz kalıyor.
   - İndirme için makul bir gövde zaman aşımı ekle (ör. 15 dk).
   - indir() (satır ~194-222) beklenen boyutun (release asset size / content-length) üstüne çıkınca dursun.
6. 📍 crates\afudm-extras\src\g1\guncelleme.rs:340-342 `ps_q`: yalnız `'` kaçırılıyor. PowerShell tek tırnaklı dizgede U+2018, U+2019, U+201A ve U+201B de tırnak sayılır. Bu karakterleri de iki katına çıkar ve test ekle.

## Kontrol (gerçek çıktıyı SONUC'a yapıştır)
- `cargo test` (kök workspace) + `cargo clippy --all-targets -- -D warnings`
- `cargo clippy --manifest-path app\Cargo.toml -- -D warnings` + `cargo test --manifest-path app\Cargo.toml`
- `python -B tests_hata\verify.py` ve `python -B tests_hata\hepsi.py --only bridge`: GECTI kalmalı.
- `cargo fmt` yalnız değiştirdiğin dosyalara.

SONUC: docs\sonuc\SONUC_FIX8.md. Soru sorup durma.
