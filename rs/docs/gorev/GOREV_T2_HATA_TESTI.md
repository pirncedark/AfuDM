# Test Ekibi T2: Hata testleri (codex)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Durum: Python ↔ Rust uyum testi 98 adımda kritik 0 (tests_parity\). Şimdi uyum değil, SAĞLAMLIK test edilecek.
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM

## ÇALIŞACAĞIN DOSYALAR
- tests_hata\ (yeni klasör): test betikleri, README
- app\Cargo.toml + app\src\test_kapisi.rs + main.rs: yalnız 4. madde (`test-kapisi` cargo özelliği)
- docs\sonuc\SONUC_T2.md
Uygulama hatası bulursan DÜZELTME: 📍 dosya:satır + yeniden üretme adımı + beklenen/gerçek davranış yaz. (Küçük ve kesin düzeltme gerekiyorsa en fazla 20 satır yapabilirsin; yaptığın her düzeltmeyi SONUC'ta ayrıca listele.)

## Kurallar
- Rust exe'yi geçici klasöre kopyalayıp çalıştır; port 6811 olmasın; veri klasörü geçici olsun.
- Kullanıcının çalışan AfuDM'ine (6810/6811, P\data) ve AfuDM.exe'ye DOKUNMA. Pencere açma. Test bitince süreçleri kapat.
- Yerel dosya sunucusu kullan, dış internete indirme yok.

## Testler
1. Hatalı girdi (fuzz): bütün POST uçlarına bozuk JSON, dev gövde (> sınır), yanlış tipler, boş alanlar, unicode, `..\` yol kaçışı, `file://` / `javascript:` adresleri, token yok / yanlış / eski token, yanlış Origin. Beklenen: hiç 500 PANIC yok, süreç ölmüyor, dosya sistemi dışına yazma yok. Python aynı girdiye ne dönüyorsa Rust da aynısını dönsün (fark varsa listele).
2. Çökme ve yeniden başlatma: büyük bir HTTP indirmesi (yerel sunucu, hız sınırlı) %40'tayken AfuDM sürecini zorla öldür (taskkill /F), yeniden başlat. İndirme kaldığı yerden devam etmeli (.aria2 kontrol dosyası, --auto-save-interval=60, session). Aynı testi torrent (web-seed) için de yap. Veritabanı bozulmamalı.
3. 2.9.8 → 3.0 güncelleme provası:
   a. Kullanıcının gerçek DB'sinin KOPYASIYLA 3.0'ı aç: P\data\afudm.db + wal + shm → geçici klasör. Ayarlar, geçmiş ve satır sayıları korunmalı, şema göçü hatasız olmalı.
   b. 2.9.x güncelleyicisi (P\core\guncelleme.py) 3.0 zip'ini açabilmeli. Zip düzenini guncelleme.py'nin beklediği gibi kur (AfuDM-v3.0.0-win64.zip içinde AfuDM\AfuDM.exe + gereken engine\ ve ui\). P\core\guncelleme.py'nin zip doğrulama ve uygulama fonksiyonlarını yerel sahte GitHub sunucusuyla geçici klasörde çalıştır ve 3.0 exe'sinin yerine geçtiğini kanıtla. Kullanıcının gerçek kurulumunu DEĞİŞTİRME.
   c. Zip'i üreten betik yoksa scripts\ altında hangi betiğin üreteceğini öner. Release iş akışı (.github\workflows\release.yml) Rust derlemesine nasıl çevrilir, SONUC'ta adım adım yaz (değiştirme).
4. Köprü test kapısı: Tauri köprü komutları (146 Api metodu) pencere olmadan çağrılamıyor.
   - app'e `test-kapisi` adlı cargo özelliği ekle. Özellik açıkken yerel bir HTTP ucu (/_test/api_call, token korumalı, yalnız 127.0.0.1) bridge::dispatch'i çağırsın. Varsayılan derlemede bu kod HİÇ derlenmesin (#[cfg(feature)]).
   - Bu kapıyla her Api metodunu en az bir kez çağıran bir betik yaz. Python tarafında aynı metodu P\app.py Api'yi headless örnekleyerek çağır; sonuç biçimlerini karşılaştır (tests_parity kalıbı). Pencere gerektiren metotları (pencere_*, klasor_gozat diyaloğu) atla ve listele.
   - Yönetim paneli (6821) ve LAN dinleyicisini bu kapıyla `sunucu_ayarla` üzerinden aç; 127.0.0.1 ve yerel IP'den erişim kurallarını (izinli/izinsiz) test et.
5. RAM ve CPU: boşta (pencere yok) 5 dk, 1 GB yerel HTTP indirmesi sırasında, 3 eşzamanlı indirme sırasında. Rust ve Python'u yan yana ölç (Working Set + Private Bytes, tüm alt süreçler dahil). Disk yazma hızı ve CPU yüzdesi de yazılsın.

## Çıktı
- `python tests_hata\hepsi.py` tek komutla 1, 2, 4 ve 5'i koşsun (3 ayrı komut olabilir).
- SONUC_T2.md: her test için GEÇTİ/KALDI tablosu ve gerçek çıktı, bulunan hatalar 📍 ile, ölçüm tablosu. Soru sorup durma.
