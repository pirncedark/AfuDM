# T2 hata ve dayaniklilik testleri

1. `python -B tests_hata/verify.py`: ozellikli exe, varsayilan exe, test ve clippy; cargo offline.
2. `python -B tests_hata/hepsi.py`: madde 1, 2, 4, 5; varsayilan bos bekleme 300 saniye.
3. `python -B tests_hata/upgrade.py`: gercek DB dosyalarinin fiziksel kopyasinda goc ve yerel sahte GitHub ile eski guncelleyici.

Gerekli: Windows, Python 3.11+, psutil, kaynak projenin mevcut Python bagimliliklari, yerel cargo onbellegi ve engine/aria2c.exe.

Tek bolum: `python -B tests_hata/hepsi.py --only resources|fuzz|crash|bridge|network|smoke` (birini sec).
Ciktilar `tests_hata/rapor/`, ozet `docs/sonuc/SONUC_T2.md`. KALDI sonucunda cikis kodu 1; 0 yalniz tum secili testler gectiyse.
`--idle-seconds` yalniz betik gelistirme icin: 300 altindaki olcum kesinlikle GECTI sayilmaz.

## Izolasyon

Her calisma kendi gecici klasorunu ve rastgele portlarini kullanir. 6810/6811'e istek gonderilmez.
Rust exe onceden derlenmis tests_hata/bin/AfuDM_test.exe dosyasindan gecici klasore kopyalanir.
Python kaynaklari salt okunur import edilir; -B/PYTHONDONTWRITEBYTECODE kaynakta pycache olusmasini onler.
Pencere/tepsi yok; engine alt surecleri CREATE_NO_WINDOW ile baslar; yalniz sahip olunan PID agaci kapatilir.
Uygulama verileri veya calisan kullanici exe'si degistirilmez. DB goc testinde canli DB acilmaz, db/wal/shm once kopyalanir.

## Kapsam siniri (GECTI diye gizlenmez)

Uretim Rust Aria2Daemon sabit 6810..6830 araligini tarar, disaridan test portu secilemez.
Bu nedenle test-kapisi ozelligi test_kapisi.rs icinde ayri boot kullanir:
uretim engine args.rs include edilir, ozel RPC portu ve DHT/LPD kapali secenekleri uygulanir;
uretim Manager, SqliteStore, HTTP router ve bridge::api_call/dispatch aynidir.
Manager'a dogrudan gercek Aria2Rpc enjekte edilir. IdleRpc sadece baslatilmayan yer tutucudur;
reliability_health/reliability_restart_engine atlanir. Otomatik engine uyku ve uretim daemon restart yolu bu testle dogrulanmaz.
Rust bos bekleme olcumu bu nedenle uretim uyku davranisiyla birebir performans karsilastirmasi degildir.
Python icin sadece yollar, RPC portu, DHT/LPD ve istege bagli otomatik motor kurucusu izole edilir.
Guncelleme, dosya secimi, clipboard, registry, pencere veya dis Internet gerektiren Api metotlari bridge_rows.json icinde nedenleriyle atlanir.
Tracker taramasini baslatacak fuzz girdileri atlanir; diger hatali girdiler uretim dogrulayicilarina gonderilir.
Yazma kacagi kontrolu bilinen hedeflerde sentinel kontroludur; tum sistem dosya islemlerinin izlenmesi degildir.
Fiziksel DB+WAL+SHM kopyasi canli sistemde atomik snapshot garantisi vermez; kopyanin integrity_check sonucu ayrica yazilir.
Guncelleme testinde mevcut kaynak 2.9.6 oldugu icin yalniz helper icinde SURUM=2.9.8 uygulanir; gercek 2.9.8 kaynak testi oldugu iddia edilmez.
Son EXE yeniden acilisi engellenir; guncelleyicinin asil PowerShell kopyalama/yedekleme yolu gercekten calistirilir.

Raporu ham ciktilardan yenile: `python -B tests_hata/report.py`.
Varsayilan EXE test kapisini veya migration modunu icermez; migration icin ozellikli tests_hata/bin/AfuDM_test.exe kullanilir.
