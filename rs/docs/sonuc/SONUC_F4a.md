# SONUC F4a: köprü G komutları
Ajan rapor dosyasını kendisi yazamadı; bu metni Claude, ajanın raporundan aktardı.

- Dosya: app/src/kopru_g.rs. bridge.rs'te yalnız görünürlük değişti: `hata`, `motor_hazir_degil`, `s`, `truthy`, `Kabuk.app` artık pub(crate).
- Bağlananlar: F4a listesindeki 28 adın tamamı. Ek olarak `eklenti_yeniden_baslat`, `eklenti_islem_iptal`, `eklenti_klasoru_ac`.
- Ad karşılaştırması: app.py Api'de 146 public metot var. F4a'da eksik yok. Bağlanmayan 6 ad F4b'nin kapsamında: security_rotate_token, seed_tracker_kaydet, tracker_klasoru_ac, tarayicidan_sor, yerelden_sor, windows (property).
- `cerez`: app.py Api'de bu adda bir metot yok, bu yüzden bağlanmadı.
- Doğrulama: clippy -D warnings exit 0; `cargo test kopru_g` 14 geçti; release build exit 0.

## Sapmalar 📍
- start_at geçersizse BAD_REQUEST yerine satır hatası dönüyor (zaman ayrıştırması çekirdekte yapılıyor).
- Chrome'un `once` geri çağrısı yok; eşleştirme, baslat'tan önce açılıyor.
- probe zaman aşımı ve RAM önbelleği Rust'ta yok.
- uuid crate'i yerine rastgele 128-bit kimlik üretiliyor.
- err.noLink metni yalnız "en" dil ayarında İngilizce.
- `_uzaktan` yolu yok.

## Yapılmayanlar
- Canlı kabuk testi yapılmadı: komutlar yalnız Tauri api_call ile çağrılabiliyor ve pencere açmak yasak.
- dispatch doğrudan test edilmedi; yalnız yardımcı fonksiyonlar test edildi.
