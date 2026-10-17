# SONUC G2: eklenti, çerez, link toplayıcı, kurallar

Not: Ajan rapor dosyasını yazamadı. Bu dosyayı Claude, ajanın raporundan aktardı.

## Dosyalar
crates/afudm-extras/src/g2/: mod.rs, eklenti.rs, eklenti_servis.rs, cerez.rs, linkgrabber.rs, kurallar.rs, py.rs, url_parca.rs

## Taşınanlar ✅
- Manifest ve paket doğrulama (zip slip, zip bomb koruması), sha256 kontrolü.
- Eklenti kur, güncelle, geri al, kaldır; ayar ve liste işlemleri.
- Çerez başlığı ve Netscape çerez dosyası.
- Link toplayıcı ve kural motoru (Python'daki `sorted(reverse=True)` uygulama sırası korundu).
- HTTP rotaları: /rules, /eklentiler, /eklenti, /eklenti/gunluk, /eklenti/islem, /linkgrabber.

## Eksik ⚠
- Eklenti sürecini çalıştırma yok; Python yorumlayıcısı gerekiyor. Etkinleştirme `BASLAMADI` döner.
  Kullanıcıda kurulu eklenti sayısı 0 (data/afudm.db plugins tablosu). Bu iş 3.1'e kaldı.
- `probe_url_info` Rust'ta yok; probe işlemi dışarıdan kapanış (closure) olarak veriliyor.
- Python hatası olduğu gibi taşındı, düzeltilmedi: `elle_geri_al` (core/eklenti.py:938) yedekte `.afup` yokken `paket_incele` çağırıyor, bu yüzden her zaman hata veriyor.

## Claude düzeltmeleri (18 Eki)
- UiBridge'e `open_linkgrabber` eklendi. /linkgrabber artık Python gibi `{"ok":true,"pending":true}` döner; arayüz yoksa 503 UI_YOK.
- SURUM sabiti "2.9.6" yerine `env!("CARGO_PKG_VERSION")` (3.0.0) oldu.

## Test
`cargo test -p afudm-extras g2`: 37 geçti, 0 başarısız. `cargo clippy -p afudm-extras --all-targets -- -D warnings`: temiz.
