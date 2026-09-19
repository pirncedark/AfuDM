# Implementation v1.7.5 to v2.3

Her surum veri modeli, backend servis, HTTP/pywebview ortak API, UI ve dogrulama senaryosu ile birlikte tasarlanir. DB migration olmadan sema degisikligi yoktur; kullanici ayarlari ve indirme gecmisi korunur. Pywebview ve HTTP API ayni servis katmanini kullanir. Bir surum uygulanip dogrulanmadan core/surum.py yukseltilmez, tag veya release atilmaz.

| Surum | Veri/backend | API/UI | Dogrulama senaryosu |
|---|---|---|---|
| v1.7.5 | Ayar migrationi, mobil cihaz kaydi, PWA | Atomik ayar RPC, mobil durum | Gecersiz alan hicbir ayari yazmaz; offline kabuk |
| v1.8.0 | Otomasyon kurallari | Kural editoru ve durum | Kural kapat/tekrar dene |
| v1.9.0 | Indirme kurallari | Etkin deger kaynagi | Ozel > kural > genel |
| v2.0.0 | Kuyruk orkestrasyonu | Kuyruk gozlemi | Iptal ve kurtarma |
| v2.1.0 | Eklenti guven modeli | Izin aciklamasi | Guvenilen eklenti siniri |
| v2.2.0 | Cihaz yonetimi | Rol/iptal ekranlari | Iptal edilen cihaz erisemez |
| v2.3.0 | Bakim ve tasima | Saglik merkezi | Hata tekrar/geri alma |
