# SONUC T1: Python ↔ Rust kara kutu uyum testi (ikinci tur)

Durum: koşu tamam, sonuç **kısmi**. Kritik fark sayısı 57'den **9**'a indi. Ama 5.x (indirme), 9.2-9.3 (paylaşım) ve 5.3/5.6 (`/indir`, `/dosya`) hâlâ KANITLANMADI: iki tarafta da indirme/paylaşım satırı oluşmadı. Torrent dosyaları SHA-256 ile doğrulandı.

## Sayılar

| Tur | Adım | Kritik | Orta | Kozmetik |
|---|---|---|---|---|
| 1 (ilk koşu, eski exe) | 90 | 57 | 34 | 0 |
| 2 (yeni exe, harness düzeltmeli) | 95 | 9 | 2 | 4 |

Çıkış kodu: 1 (kritik var). Ham sonuç: `rs\tests_parity\rapor\sonuc_son.json`.

## Test ortamı (ikinci tur)

- Rust: `rs\app\target\release\AfuDM.exe` geçici klasöre kopyalandı (F3 + Entegrasyon-3 düzeltmeleri dahil güncel derleme). Koşu sırasında kaynak exe yeniden derlenmedi.
- Python: `C:\Users\afuuu\Desktop\afuproject\AfuDM` kaynağı, veri `AFUDM_DATA_ROOT` ile geçici klasörde, `kaydetme_penceresi=false`.
- `P\data` imzası: koşu sonunda **değişmiş** (`P\data degismedi: False`). Değişen dosya `afudm.db-wal`; yazım test bittikten sonra (03:04:17) da sürdü. Bu, yazımın kullanıcının çalışan AfuDM'inden (PID 29328, 6811) geldiğini gösteriyor; harness Python'un DB yolunu geçici klasöre çevirdiği için yazmış olması beklenmez. Yine de **kesin kanıt yok**. Kullanıcı açısından: test kendi veri klasörüne yazmadı; P\data'ya kendi başına yazan çalışan uygulamanın etkisi.
- Kullanıcının 6811 AfuDM'i ve 6810 aria2'si yerinde, yanıt veriyor.

## Doğrulanan (kanıtlanmış eşitlik)

- Torrent (web-seed, yerel): metadata 6.1b'de hazır oldu, iki tarafta `paket/a.bin` ve `paket/b.bin` dosyaları diskte kaynakla **SHA-256 birebir** (6.11, 6.12).
- Çekirdek, ayarlar, ekleme, kontrol, kurallar, eklenti, blob, handoff, token rotasyonu: iki tarafta aynı durum kodu ve anahtar kümesi.
- Yerel H statik dosyaları (`/m`, manifest, i18n, sw, ikon): artık iki tarafta 200.

## Kalan kritik farklar (9)

1. **4.2 `/control resume`**: Python 500 ("beklenmeyen bir sunucu hatası", aria2 `unpause` hatası), Rust 200.
   📍 `rs\crates\afudm-api\src\lib.rs` `control` içinde `"resume" => ctx.manager.resume(gid).map(|_| json!({}))` (≈satır 370). Rust gid'i kabul edip 200 döndü; Python aynı gid için aria2 hatası aldı. Hangi durumda Rust'ın yanlış 200 verdiği doğrulanmalı (indirme zaten tamamlanmış olabilir).
2. **5.1 indirme bekleme (her iki taraf)**: `/snapshot` iki tarafta da boş (`gorulen=[]`), `satir_yok`. Python tarafında a.bin diskte kaynakla eşleşti (5.3d), yani indirme olmuş. Python'un `py.log` kaydı (koşu sonrası kalan dosya): `/dosya` ve paylaşım adımlarında `aria2.tellStatus: GID ... is not found`. Yani tamamlanmış indirmenin gid'i aria2'den düşmüş; gid tabanlı uçlar (`/indir`, `/dosya`, `/share_create`, snapshot satırı) bitişten sonra çalışmıyor. Bu, Python'un davranışı olabilir (tamamlanınca gid temizliği) ya da harness'ın gid'i geç kullanması. **Kök neden açık**; kaynakta kesin temizlik noktası bulunamadı (`P\core\manager.py` 531, 879, 1328, 2599 satırları incelendi, kesin değil). Rust tarafı için de aynı kontrol gerekli. Harness, gid'i yakalayan `/add` yanıtını doğru okuyor (3.1); `interactive` yolu harness'ta gönderilmiyor, dolayısıyla bekleyen kuyruk değil. Python `snapshot()` (P\core\manager.py ≈1695-1760) aria2 + DB satırlarını birleştiriyor. Sonraki tur: `/snapshot` ham gövdesini ve DB satırlarını rapora yazmak.
3. **5.3d a.bin disk SHA-256 (Rust)**: diskte `a.bin` bulundu ama içeriği kaynakla eşleşmiyor. Python'da eşleşiyor.
   📍 Rust indirme yazımı: `rs\crates\afudm-core\src\queue` ve `afudm-engine` tarafı (aria2 `--dir`). Rust'ın dosyası tam mı, kısmi mi, başka içerik mi: bilinmiyor. Sonraki turda aday dosyanın boyutunu ve hash'ini raporlamak gerekir (harness şu an yalnız bulundu/eşleşmedi döndürüyor).
4. **`/control ayarla` 4.3** (kozmetik+orta): iki taraf da 400, metin farklı (`canli degistirilemedi` ön eki aynı, sonrası farklı). Orta.
5. **`/renew` 7.3** (orta, metin): iki taraf 400, metin farklı (aria2 gid mesajı vs "indirme bulunamadi"). Rust metni Python'a uydurulabilir.
6. **8.11 `/reliability/diagnostics-preview` mesaj** (kozmetik).

## Bilinen sınır: "fark yok" ama kanıt yok

Aşağıdakiler iki tarafta da **404** döndü; `beklenen` kontrolü ancak 200/206'da çalışır. Sınıflandırıcı bunları yanlışlıkla "fark yok" saydı. Gerçek durum: **doğrulanmadı**.

- 5.3 `/indir?gid=` (beklenen a.bin)
- 5.6 `/dosya?gid=&k=` (beklenen a.bin)
- 9.2 `/s/<kod>` (beklenen a.bin), 9.3 Range (ilk 100 bayt)

Düzeltme (harness, sonraki tur): `beklenen` / `beklenen_kesit` içeren adım 200/206 dönmezse kritik `kanit_yok` farkı üretilmeli. Bu, 5.x kök neden çözülene kadar 9.2-9.3'ü kırmızı tutar.

## Sonraki adımlar

1. 5.x kök neden: `/snapshot` ham gövdesini ve DB satırlarını rapora yaz; gid eşlemesini doğrula.
2. Harness: `kanit_yok` kuralını ekle; disk adayının boyut/hash'ini raporla.
3. Rust: `resume` davranışı (📍 lib.rs ≈370) ve Rust a.bin içeriği (indirme yazımı) incelenmeli.
4. Sonra yeniden koş; 5.x/9.x `kanit` olmadan "geçti" yazılmaz.
