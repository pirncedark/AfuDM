# Entegrasyon-6: T2 bulgularını kapat (iki codex, paralel)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Bulgu raporu: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_T2.md ("📍 Yeniden üretilebilir bulgular" bölümü ve sonrası)
Test araçları: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\tests_hata\ (README'ye bak)
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM
Kullanıcının çalışan AfuDM'ine (6810/6811), P\data ve AfuDM.exe'ye DOKUNMA. Pencere açma. Test süreçlerini sonunda kapat; Temp\afudm_* altında kendi başlattığın python/aria2c kalmasın.

## 6a: Köprü biçim farkları → YALNIZ app\src\ (bridge.rs, kopru_g.rs, kopru_h.rs)
SONUC_T2'de 📍 ile işaretli 19 köprü metodunun yanıt biçimini Python Api ile birebir yap:
automation_cancel, automation_retry, bekleyen_iptal, butunluk_hepsini_tara, control, link_yenile, motor_durumu, reliability_recovery_preview, reliability_restore, retry, sistem_durumu, surum_bilgi, torrent_dosyalari, torrent_metrikleri, torrent_on_ekle, torrent_secimi_ayarla, windows_integration_apply / remove / status / test.
Her biri için Python referans satırı raporda var.
Kontrol: `python -B tests_hata\hepsi.py --only bridge` → KALDI kalmasın (pencere gerektirenler hariç, listesi raporda).
SONUC: docs\sonuc\SONUC_FIX6a.md

## 6b: HTTP gövde farkları + çökme sonrası devam → YALNIZ crates\ ve tests_hata\
1. tests_hata karşılaştırması gürültülü: gid, id ve anahtar sırası gibi değişken değerler fark sayılıyor. Karşılaştırmayı tests_parity'deki gibi ŞEKİL bazlı yap (anahtar kümesi + tip + durum kodu).
2. Gerçek gövde farkları: ör. g2 /eklenti bozuk gövde Rust'ta "BAD_REQUEST", Python'da "GOVDE_HATASI" + metin. Python'un govde okuma hatalarını (P\api\server.py GovdeHatasi / _govde_oku) bütün rotalarda birebir uygula.
   Dev gövde: Python bağlantıyı kesiyor, Rust 413 dönüyor. Rust davranışı kalsın; daha güvenli, SONUC'ta not düş.
3. Çökme sonrası devam (hem Python hem Rust'ta KALDI). %40'ta zorla öldürülen HTTP indirmesi yeniden açılınca devam etmiyor, SHA uyuşmuyor. `--save-session-interval=0` bilerek kapalı (session dosyası çerez ve başlık sırrı tutuyor, açma).
   Çözüm Rust'ta: açılışta DB'deki bitmemiş satırları (active/waiting/paused, kind http/torrent) aria2'deki işlerle karşılaştır. aria2'de olmayanları aynı dir/out/seçeneklerle ve --continue ile yeniden ekle. Böylece .aria2 kontrol dosyasından kaldığı yerden devam eder.
   - Duraklatılmışsa yine duraklatılmış eklensin.
   - Gizli başlık/çerez DB'de nasıl tutuluyorsa (Python restore / pending yolu) oradan alınsın.
   - DB satırının gid'i yeni gid ile güncellensin.
   Python'da da aynı hata var. Python'a dokunma; SONUC'ta 📍 ile Python düzeltme önerisini yaz.
   Kontrol: `python -B tests_hata\hepsi.py --only crash` → Rust http ve torrent GEÇTİ.
4. `cargo test` (kök workspace) + clippy -D warnings yeşil.
SONUC: docs\sonuc\SONUC_FIX6b.md
