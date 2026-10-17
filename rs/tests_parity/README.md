# tests_parity: Python ↔ Rust kara kutu uyum testi (T1)

Aynı HTTP istek dizisini eski Python AfuDM'e ve yeni Rust AfuDM.exe'ye gönderir;
yanıtların şeklini ve indirilen dosyaların gerçek içeriğini (SHA-256) karşılaştırır.

## Çalıştırma

    python rs\tests_parity\uyum_testi.py

- Python: `C:\Users\afuuu\Desktop\afuproject\AfuDM` kaynağından, headless benzeri
  (`core.baslangic.uyku_yollarini_ayarla` + `LocalAPI`). Yalnız okunur kullanılır;
  `PYTHONDONTWRITEBYTECODE=1` ile bytecode yazılmaz. Başlangıçta
  `kaydetme_penceresi=false` ayarlanır.
- Rust: `rs\app\target\release\AfuDM.exe` geçici klasöre kopyalanır, `AFUDM_PORT` ile
  çalışır; aria2c kopyalanır. Derleme kilidi oluşmaz.
- Veriler geçici klasörde (`%TEMP%\afudm_t1_*`); bitince süreçler ve klasör silinir.
- Kullanıcının 6811 AfuDM'i ve `P\data` klasörü test öncesi/sonrası imza ile kontrol edilir.
- Çıkış kodu: `0` kritik fark yok, `1` kritik fark var, `2` kurulum hatası.

## Dosyalar

- `uyum_testi.py`: harness.
- `senaryolar\temel.json`: adımlar (95). Her adım:
  - `yontem`, `yol`, `kimlik` (`T` varsayılan, `yok`, `bozuk`), `baslik`, `govde`,
    `ham` (blob), `ham_metin` (bozuk JSON), `satir_gid`.
  - `yakala`: yanıttan değişken al (`{"gid_a": "gid"}`).
  - `bekle`: `{"gid": "gid_a", "sn": 150}`: indirme `complete` olana dek `/snapshot` yokla.
    Başarı yalnız `complete` ile. Görülen gid'ler ve durumlar rapora yazılır (teşhis).
  - `bekle_hazir`: torrent metadata'sı (`/torrent/dosyalar` `hazir_degil=false`) olana dek bekle.
  - `disk`: `{"ad": "paket/a.bin", "kaynak": "paket/a.bin", "sn": 150}`. Her tarafın
    indirme klasöründe yol sonu eşleşen dosyaları bulur; SHA-256'sı kaynak dosyayla
    aynı olan en az bir aday olmalı. `sn` süresince dosya görünene dek bekler.
  - `beklenen`: binary yanıt gövdesi kaynak dosyayla birebir aynı olmalı.
  - `beklenen_kesit`: Range yanıtı kaynağın ilk N baytı olmalı.
- Yer tutucular: `{fs}`, `{fs_q}`, `{token}`, `{gid_*}`, `{paylasim}`.
- `rapor\sonuc_son.json`: son koşunun adım adım ham sonucu (token içermez).

## Karşılaştırma kuralları

- Durum kodu, `content-type`, `Access-Control-Allow-Origin` varlığı, ek başlıklar ve
  JSON anahtar kümesi/tipleri karşılaştırılır. Değerler karşılaştırılmaz (gid, zaman,
  yol), istisna: `ok`, `error`, `code`, `neden` (hata metni).
- Doğrulama kuralları (ikinci tur):
  - `bekle` adımı: her iki tarafta `complete` olmalı, yoksa **kritik** `indirme_tamamlanmadi`.
  - `disk` adımı: her iki tarafta `sha_ok` olmalı, yoksa **kritik** `dosya_icerigi`.
  - `beklenen` / `beklenen_kesit`: içerik kaynakla uyuşmazsa **kritik** `govde_kaynakla_uyusmuyor`.
- Sınıflar:
  - **kritik**: durum kodu, Rust'ta eksik anahtar, `ok`, CORS izin başlığı, indirme/içerik doğrulaması.
  - **orta**: fazla anahtar, tip farkı, hata metni/kodu, ek başlık, ikili gövde farkı.
  - **kozmetik**: mesaj metni, boş/dolu liste.

## Bilinen kapsam sınırları

- `/show`, `/linkgrabber` UI yolu, `/_listener/quit|exit|notify`, `POST /windows-integration`
  bilerek kullanılmaz (pencere açma, uygulamayı kapatma, bildirim, kayıt defteri).
- Rust `/capabilities` Store kaydı yoksa 503 döner (API_SOZLESME madde 1).
- Yerel dosyalar `http.server` ile 127.0.0.1 üzerinde; dış internete çıkılmaz.
- Rust aria2 RPC portu koddan sabit (6810-6830). Rust kopyası kendi geçici secret'i ile
  çalıştığı için kullanıcının aria2'sine bağlanmaz.
- Koşu gerçek indirme yaptığı için yerel web-seed ve dosya sunucusu gerekir; süre ~10 dk.
