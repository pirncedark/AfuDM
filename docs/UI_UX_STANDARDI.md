# UI UX Standardi

## Degismez teslim kurali

Bir ozellik ancak arayuzden bulunabiliyor, kullanilabiliyor, yapilandirilabiliyor, acilip kapatilabiliyor, canli durumu izlenebiliyor, hatasi anlasilip yeniden denenebiliyor veya iptal edilebiliyorsa tamamdir. Sadece API, CLI veya calisir gorunen placeholder teslim degildir.

| Boyut | Zorunlu kanit |
|---|---|
| Bulunabilirlik | Arama ve anlamli baslik |
| Kullanim | Calisan eylem ve sonuc |
| Yapilandirma | Kalici, dogrulanmis ayar |
| Izleme | Canli durum ve zaman |
| Hata cozumu | Acik hata, tekrar/iptal |
| Kalicilik | Yeniden acilista korunma |

Ayar onceligi: indirmeye ozel secim -> eslesen kural -> genel varsayilan. Arayuz etkin degerin kaynagini gostermelidir. Uygulanma rozetleri: hemen, yeni indirmelerde, sonraki baslatmada, servis yeniden baslayinca. Surum kabul kapisi: backend, UI, hata, yeniden deneme/iptal, kalicilik, i18n ve responsive kontrolu birlikte tamamlanir.

## Durustluk kurallari

Torrent aramasi hiz veya seed garantisi vermez. Ozel torrentlere dis tracker eklenmez. Kurtarma ekrani kesin basari vaat etmez. Eklenti izin ekrani gercek izolasyon gibi sunulmaz: ilk asama guvenilen eklenti modelidir. "Sandbox var" ifadesi yanlis guvenlik iddiasi olarak kullanilmaz.
