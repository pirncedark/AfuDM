# Test Ekibi T1: Python ↔ Rust kara kutu uyum testi (claude kod ajanı)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
API sözleşmesi: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\API_SOZLESME.md
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU, ÇALIŞTIRILABİLİR): P = C:\Users\afuuu\Desktop\afuproject\AfuDM

Amaç: Aynı HTTP istek dizisini hem eski Python AfuDM'e hem yeni Rust AfuDM.exe'ye gönder. Yanıtların biçimini karşılaştır: alan adları, tipleri, durum kodları, hata gövdeleri. Farkları raporla. "Çalışıyor" iddiası bu teste dayanacak.

## ÇALIŞACAĞIN DOSYALAR
- rs\tests_parity\ (yeni klasör): uyum_testi.py, senaryolar\*.json, README.md
- docs\sonuc\SONUC_T1.md
Kod düzeltmesi YAPMA; yalnız test yaz ve farkları raporla.

## Kurallar
- İki uygulama da GEÇİCİ veri klasörüyle ve 6811 DIŞI portlarla çalışsın.
  - Python'u kaynaktan headless başlat. Nasıl yapıldığını P\tests\headless_test.py ve P\tests\local_api_startup_test.py gösteriyor. Taşınabilir mod, AFUDM_DATA ve benzeri ortam değişkenlerini P\core\paths.py'den öğren.
  - Rust: rs\app\target\release\AfuDM.exe (AFUDM_PORT ve geçici veri klasörü yöntemi docs\sonuc\SONUC_F.md'de).
  - Kullanıcının çalışan AfuDM'ine (6811) ve P\data klasörüne ASLA dokunma. Pencere açılmasın.
- Token: her uygulamanın kendi api_token.txt / api_endpoint.json dosyasından oku.
- Yerel dosya sunucusu (http.server) ile küçük test dosyaları ver. Dış internete indirme yok.

## Senaryolar (en az)
1. /ping, /capabilities, /snapshot (boş)
2. /settings GET + geçerli POST + geçersiz POST (hata metni aynı mı)
3. /add: HTTP dosyası; kopya ekleme; geçersiz URL; file:// reddi; token yok (401); yanlış Origin
4. /control: pause, resume, remove, remove+delete_files, pause_all, resume_all, ayarla
5. İndirme bitişi → /snapshot satırının alanları (Python ile aynı anahtar seti)
6. Torrent: yerel .torrent (web-seed ile yerel HTTP'den) → /torrent/dosyalar (hazir_degil biçimi), /torrent/secim, /torrent/metrik, /peers
7. /probe, /renew, /tracker/tara, /seed*, /mode, /token/rotate
8. /rules GET/POST, /eklentiler, /linkgrabber (UI yokken 503 beklenir, iki tarafta da)
9. /share_create + /s/<kod> + /pair (yerel)
10. /add_blob, /handoff/error, /dosya, /indir, /klasorler
Karşılaştırma: değerler değil, ŞEKİL (anahtar kümesi + tip + durum kodu). gid, zaman ve yol gibi değişken değerleri yok say. Farkları "kritik" (eklenti ya da arayüz kırılır), "orta" ve "kozmetik" diye sınıfla.

## Çıktı
- `python rs\tests_parity\uyum_testi.py` tek komutla iki uygulamayı da açar, senaryoları koşar, kapatır; çıkış kodu 0 = kritik fark yok.
- SONUC_T1.md: senaryo başına GEÇTİ/FARK tablosu, her fark için 📍 Rust dosya:satır tahmini + Python karşılığı.
- Rust exe'yi başka bir ajan şu an yeniden derleyebilir. Exe'yi doğrudan ÇALIŞTIRMA: önce geçici bir klasöre kopyala (rs\app\ui klasörü ve engine yolu gerekiyorsa onları da). Kopyayı çalıştır; böylece derleme kilitlenmez. Exe kilitliyse ya da eskiyse bekleme; test betiğini bitir ve var olan exe ile koş.
