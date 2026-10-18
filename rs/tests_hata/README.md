# Rust hata ve dayanıklılık testleri

Depo kökünden:

1. `python -B rs/tests_hata/verify.py`: test kapılı ve varsayılan Rust derlemeleri, test, clippy, biçim kontrolü.
2. `python -B rs/tests_hata/hepsi.py`: resources, fuzz, crash, bridge, network. Boşta ölçüm 300 saniye; tüm aşamalar geçmezse çıkış 1.
3. `python -B rs/tests_hata/upgrade.py --snapshot-dir <cevrimdisi-kopya>`: Rust SQLite göçü, bütünlük, satır sayıları ve içerik korunması. Canlı kullanıcı verisi okunmaz.
4. `python -B rs/tests_hata/report.py`: ham çıktılardan rapor.

Gerekli: Windows, Python 3.11+, psutil, yerel Cargo önbelleği, `engine/aria2c.exe`.
Çıktı: `rs/tests_hata/rapor/`. Her uygulama geçici klasör ve rastgele port kullanır; 6810/6811 yasaktır. Pencere açılmaz, yalnız sahip olunan süreçler kapatılır.

`bridge_cases.json` arşivden alınmış sabit girdi envanteridir; Python uygulamasını okumaz veya başlatmaz. Yanıtlar Rust durum kodu ve istisna kontrollerinden geçer. Geçerli kurtarma girdileri ayrıca sınanır.

Test kapısı gerçek Rust Manager, SQLite deposu, HTTP router ve bridge kullanır. Üretim daemon port taraması yerine izole motor başlatır. Registry, clipboard, pencere, dış ağ ve üretim daemon yeniden başlatma işlemleri gerekçeleriyle atlanır. Kaynak ölçümü üretimin otomatik motor uykusunu doğrulamaz. Dosya kaçışı bilinen hedeflerde sentinel ile kontrol edilir.

Eski Python karşılaştırması ve Python güncelleyici testi arşivlendi: `python-arsiv-3.0.1` etiketi. `rs/tests_parity/` kaldırıldı.
