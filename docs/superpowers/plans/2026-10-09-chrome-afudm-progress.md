# İlerleme — Chrome → AfuDM tek pencere

Başlangıç: 91b6b94. Kullanıcının test_cancel.js dosyası korunmuştur.

- Tıklama-anı aktarımı: uygulandı; Node davranış testi geçti.
- Bekleyen request_id tekrarları: atomik tekilleştirme ve restart testi 6/6 geçti.
- Torrent türü: doğrudan ve eski onCreated yolu düzeltildi.
- HTTP aktarımı 5/5, metrik 16/16 ve indirme penceresi JavaScript testleri geçti.
- Gerçek izole Chromium + aria2: 4 senaryo geçti; doğrudan bağlantılarda
  sıfır Chrome indirme olayı ve tek gerçek AfuDM dosyası doğrulandı.
- Yeni dist_test/AfuDM.exe derlendi; embedded EXE doğrulaması geçti.
- ZIP paket içerik testi yeni betiği doğruladı.

Karar: Belirsiz kabulde otomatik Chrome geri dönüşü yapılmıyor; aynı dosyanın
iki motor tarafından indirilmesi önleniyor. Kullanıcıya TR/EN yeniden deneme
bildirimi veriliyor. Normal eklenti menüsü yeniden deneme yoludur.

Kalan: Onaylanmış ve kuyruktan kaldırılmış isteklerin kalıcı kabul makbuzu;
aynı kimlikle güvenli tekrar gönderim. Görünür Chrome + paket EXE elle testi.
Tıklama/kabul/motor başlangıcı süre raporu.

Tam standart test koşusu: scripts/test.ps1 — 87 test dosyası geçti, 0 başarısız.

Sınır: Uzantısız, download niteliği taşımayan dinamik sunucu indirmelerinde
eski onCreated yolu kullanılır; bu akışta Chrome kaydetme penceresinin hiç
görünmemesi henüz garanti edilmez. Çalışan root EXE değiştirilmedi.
