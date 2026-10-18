# Ekip F3: Köprüyü tamamla (claude kod ajanı)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Durum raporu: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_F.md ("henüz yok" listesi)
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM

Amaç: Python app.py'deki Api sınıfının HER metodu Rust'ta çalışır olsun. "henüz yok" dönen tek komut kalmasın.

## ÇALIŞACAĞIN DOSYALAR
- app\ altında her şey
- crates\afudm-core\src\queue.rs ve queue\ alt modülleri: yalnız dışa açma (pub) ve 1. maddedeki taşıma
- crates\afudm-engine\src\ : yalnız 2. madde
- crates\afudm-extras\src\g1\, g2\, h\ : yalnız arayüzün ihtiyaç duyduğu pub fonksiyonu eklemek için
- docs\sonuc\SONUC_F3.md
DOKUNMA: afudm-types, afudm-core\src\lib.rs (sözleşme değişikliği gerekiyorsa SONUC'ta iste).

## Yapılacaklar
1. Core dışa açma: queue içindeki detect_kind, is_supported_source, magnet_infohash, guess_name, clean_title, gecmis_sources, find_duplicate, hiz_limiti_kb, apply_settings `pub` olsun. Python app.py kaydet_bilgi (436) ve probe_link (459) için gereken probe_url_info core'da yoksa `queue::probe_url_info(m, url)` olarak taşı. Sonra kaydet_bilgi ve probe_link köprülerini bağla.
2. reliability_restart_engine: afudm-engine'de daemon'u yeniden başlatma yolu aç (IdleRpc/daemon'a `restart()` ya da kabuğun daemon'u elinde tutması). Python reliability.restart_engine birebir: save_session → stop → start → manager.rpc'yi yenisiyle değiştir.
3. SONUC_F.md "henüz yok" listesindeki her komut. Her biri için Python app.py'deki Api metodunu oku ve aynısını yap:
   - linkgrabber_*, rules_*, download_rules, cerez
   - automation_jobs listeleri, chrome_*, eklenti uçları (kur, incele, ayar, günlük)
   - sunucu_*, sunucu_anahtar_*, start_pairing, share_*, dosya_sec_ve_paylas, agda_paylas, telefon_*
   - add_links, link_yenile, clear_finished, settings_save, proxy_testi, port_durumu, ayar_rozetleri, loglar, defender_scan, dosya_ac, item_yolu, panoya_*, probe
   - Ayrıca app.py Api'de olup köprüde HİÇ olmayan metot varsa bul: Api'deki tüm public metot adlarını tauri_kopru/bridge listesiyle karşılaştır, farkı SONUC'a yaz ve bağla.
4. LinkGrabber paneli: Python on_linkgrabber pencereye nasıl iletiyor (evaluate_js ile hangi JS fonksiyonu)? Aynısını yap. Pencere kapalıysa aç, ve sayfa hazır olunca olayı ilet (olay kaybolmasın).
5. Güncelleme zamanlaması: Python'da otomatik kontrol ui/app.js `guncellemeOtomatikKontrol` içinde (açılışta + saatte bir, 24 saat önbellek). Pencere kapalıyken de çalışması için kabuğa arka plan zamanlayıcı koy: açılıştan 2 dk sonra, sonra 6 saatte bir kontrol; otomatik güncelleme açıksa indir, boştayken uygula (Python guncelleme_uygula(otomatik=True) kuralları).
6. Video tamamlanma bildirimi şu an snapshot çağrısına bağlı. Pencere kapalıyken snapshot çağrılmıyorsa kabukta 2–5 sn aralıklı hafif bir yoklama döngüsü kur (Python manager'daki izleme döngüsü eşdeğeri; aralığı Python'dan al).
7. shutdown_when_done / sleep_when_done (SONUC_FIX2 açık kalan): Python'daki yerden taşı.
8. torrent_dosyalari artık `Json` ({dosyalar, hazir_degil, neden, gid}) dönüyor; SONUC_F'deki "hazir_degil=false varsayıldı" sapmasını düzelt.

## Kontrol
- `cargo clippy --manifest-path app\Cargo.toml -- -D warnings`, `cargo test -p afudm-core -p afudm-extras -p afudm-engine` ve `cargo build --release --manifest-path app\Cargo.toml` yeşil olmalı.
- Headless uçtan uca: 6811 dışı port, geçici veri klasörü; /add ile HTTP indirmesi + yerel .torrent ile torrent indirmesi (iki yerel aria2 tohumlayıcı ya da web-seed) + /snapshot.
- Pencere AÇMA. Test bitince başlattığın süreçleri kapat.
SONUC: docs\sonuc\SONUC_F3.md, bağlanan komut listesi ve gerçek çıktılarla. Soru sorup durma.
