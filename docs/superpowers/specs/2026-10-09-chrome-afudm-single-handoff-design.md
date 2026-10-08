# Chrome → AfuDM Tek Pencere Aktarımı

## Amaç

Kullanıcı bir indirme bağlantısına bastığında Chrome'un ayrı bir indirme veya
"Farklı kaydet" penceresi açmadan isteği AfuDM'e devretmesi; AfuDM'in tek
mevcut indirme penceresinde isteği göstermesi.

## Kanıtlanan sorun

Mevcut uzantı yalnızca `chrome.downloads.onCreated` ile çalışır. Bu olay
Chrome indirmeyi ve kullanıcının etkinleştirdiği kaydetme arayüzünü başlattıktan
sonra gelir. Eklenti indirmeyi daha sonra iptal etse bile Windows dosya seçicisi
görünür. Bu, aynı kullanıcı eylemi için iki arayüzün görünmesine yol açar.

## Karar

Uzantı, sayfa üzerindeki doğrudan indirilebilir bağlantıları belge başlangıcında
yakalar. Bağlantı indirme olarak sınıflandırıldıysa tıklama varsayılanını
engeller ve bağlantıyı arka plan işçisine gönderir. Arka plan işçisi önce
AfuDM'in yerel API'sinin ulaşılabilir olduğunu doğrular, sonra isteği doğrudan
`/add` sınırına gönderir. AfuDM isteği kabul ederse yalnız kendi mevcut indirme
penceresini öne getirir. Chrome `downloads` olayı oluşmaz.

Sınıflandırma; `download` niteliğini, bilinen indirilebilir uzantıları ve
indirme niyeti taşıyan erişilebilir bağlantı etiketlerini kullanır. Bağlantı
normal bir sayfaya yöneliyorsa uzantı hiçbir şey yapmaz. Sunucunun yalnız yanıt
başlığında indirme olduğunu bildirdiği ve sayfadan önceden ayırt edilemeyen
dinamik akışlarda mevcut `downloads.onCreated` yolu güvenli geri dönüş olarak
kalır; AfuDM kabul edemezse Chrome indirmesi tekrar başlatılır ve kullanıcı
tek cümlelik bildirim görür.

## Veri akışı

1. Kullanıcı bir indirme bağlantısına basar.
2. `extension/download-preflight.js` tıklamayı yakalar ve uygun bağlantıda
   Chrome gezinmesini durdurur.
3. Arka plan işçisi istek için URL, sayfa referansı ve sayfa kimliğini alır.
4. İşçi, bir kez AfuDM'e gönderir; mevcut çerez aktarımı yalnız hedef URL için
   ve bellekte kalır.
5. AfuDM isteği bekleyen indirme olarak ekler ve aynı `IndirmePenceresiApi`
   penceresini öne getirir; ikinci AfuDM penceresi oluşturmaz.
6. Kabul yanıtı gelmezse işçi Chrome'a yalnız bu bağlantı için güvenli geri
   dönüş navigasyonu verir. Hata "AfuDM'e ulaşılamadı; yeniden deneyin." olur.

## Tekilleştirme

Eklenti, aynı URL ve aynı sayfa bağlamı için kısa ömürlü bir bekleyen/kabul
anahtarı taşır. Hızlı tekrar tıklamalar tek API isteğine birleşir. AfuDM
sunucusu da bekleyen isteklere kaynak tabanlı kısa süreli tekilleştirme uygular;
bu, servis işçisinin yeniden göndermesiyle ikinci kayıt oluşmasını engeller.
Kullanıcının bilinçli tekrar indirmesi için pencere kapandıktan veya makul
bekleme süresi geçtikten sonra yeni istek serbesttir.

## Torrent ve görsel sınırları

`magnet:` ve `.torrent` bağlantıları tek bir torrent isteği olarak aktarılır.
Sayfa içi kapaklar, küçük resimler ve parça dosyaları otomatik indirme
aktarımı için aday değildir. Kullanıcının bir görsel bağlantısında özellikle
"AfuDM ile indir" seçmesi mevcut açık eylem yoluyla çalışmaya devam eder.

## Durum ve hız bilgileri

AfuDM isteği kabul ettiği anda listede "Başlatılıyor" görünür. Motor
metrikleri gerçek indirilen/toplam bayt, hız ve kalan süre ile güncellenir.
Toplam boyut bilinmiyorsa yalnız indirilen miktar gösterilir; uydurma yüzde
veya süre gösterilmez. Duraklat/devam/tamamla aynı kayıt üzerinden ilerler.

## Hata ve gizlilik

Kullanıcıya yalnız anlaşılır, tek cümlelik hata gösterilir. Teknik ayrıntı
yerel tanı günlüğüne gider. Çerezler ve yetkilendirme başlıkları kalıcı
kayıtlara veya tanı raporuna yazılmaz.

## Başarı ölçütleri

- Bilinen indirme bağlantısında Chrome indirme olayı ve Windows "Kaydet"
  penceresi oluşmaz.
- AfuDM'de bir kez, mevcut indirme penceresi görünür.
- Hızlı çift tıklama tek bekleyen/AfuDM kaydı üretir.
- Eşzamanlı farklı bağlantılar ayrı kayıtlar üretir.
- AfuDM erişilemezse Chrome yalnız bir geri dönüş indirmesi başlatır.
- Torrent/magnet tek işe dönüşür; otomatik görsel gürültüsü oluşmaz.
- Paket ve gerçek Chrome uçtan uca testleri davranışı doğrular.

## Kapsam dışı

Sunucunun indirme yanıtını yalnız yönlendirme sonrasında açıkladığı, sayfada
önceden ayırt edilemeyen her olası özel JavaScript akışını Chrome uzantısı
API'leriyle eksiksiz engellemek mümkün değildir. Bu akışlar güvenli geri
dönüş yolunu kullanır; desteklenen doğrudan indirme bağlantılarında ikinci
pencere oluşmaması zorunludur.
