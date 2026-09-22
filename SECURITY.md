# Güvenlik Politikası (Security Policy)

## Desteklenen Sürümler
AfuDM için güvenlik güncellemeleri yalnızca en son kararlı (stable) sürüm için sağlanır. Kullanıcıların olası açık kapılardan (vulnerability) etkilenmemesi adına her zaman uygulamanın en son sürümünü kullanmaları önerilir.

| Sürüm | Destekleniyor mu? |
|-------|-------------------|
| >= 2.7.x | :white_check_mark: Evet |
| < 2.7.x  | :x: Hayır |

## Güvenlik Açığı Nasıl Bildirilir?

AfuDM'de bulduğunuz herhangi bir güvenlik açığını veya kritik hatayı (örneğin eklenti izolasyonu ihlalleri, RCE, bilgi sızdırma) **lütfen GitHub Issues üzerinden Halka Açık (Public) olarak PAYLAŞMAYIN.**

Bunun yerine, lütfen şu adımları izleyin:
1. GitHub deposunda bulunan **Security -> Advisories** (Güvenlik Tavsiyeleri) bölümünden özel bir rapor oluşturun (Report a vulnerability).
2. Ya da doğrudan geliştirici ekibe özel e-posta (veya Discord/Telegram) ile ulaşın.

Bildiriminize şunları eklediğinizden emin olun:
- Açığın türü (ör: XSS, RCE, Yetki Yükseltme).
- Hangi sürümde ve hangi platformda test edildiği.
- Açığın nasıl tetikleneceğine dair adım adım yeniden oluşturma (Proof of Concept) senaryosu.

Bildirimlerinize en geç **48 saat** içinde yanıt vermeye ve açığı doğrular doğrulamaz kapalı bir dal (private branch) üzerinde çözmeye gayret edeceğiz. Teşekkür ederiz!
