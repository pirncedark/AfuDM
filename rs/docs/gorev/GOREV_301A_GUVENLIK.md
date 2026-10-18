# 3.0.1-A: Ertelenen güvenlik maddeleri (codex)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_301\rs\docs\EKIP_KURALLARI.md
Çalışma dizini (worktree, dal feat/3.0.1): C:\Users\afuuu\Desktop\afuproject\AfuDM_301
DOKUNMA: C:\Users\afuuu\Desktop\afuproject\AfuDM ve AfuDM_rs klasörleri, kullanıcının çalışan AfuDM'i (6810/6811) ve data\ klasörü. Pencere açma.
Paralelde başka bir codex (3.0.1-B) aynı worktree'de crates\afudm-core\src\queue\* ve crates\afudm-engine üzerinde çalışıyor; o dosyalara DOKUNMA.
YIKICI GIT YASAK: restore / checkout -- / reset / clean / stash / rebase / amend / push / switch / commit.

## ÇALIŞACAĞIN DOSYALAR
- rs\app\src\yonetim.rs
- rs\crates\afudm-extras\src\h\ (eşleştirme / mobil sayfa / esleme.rs) ve rs\app\ui\ altındaki mobil sayfa (m.html / mobil js; adını grep ile bul)
- rs\crates\afudm-api\src\listener.rs
- ilgili test dosyaları, rs\docs\sonuc\SONUC_301A.md
Başka dosya gerekiyorsa dur ve SONUC'ta sor. Her düzeltmeye birim testi ekle.

## Maddeler
1. 📍 rs\app\src\yonetim.rs:552 civarı: `sunucu_proxy_guven` açıkken istemci IP'si X-Forwarded-For'un son değerinden alınıyor. LAN'daki bir istemci bu değeri sahteleyip hız sınırını ve hatalı giriş kilidini (yonetim.rs:589, 646) atlatabiliyor.
   Çözüm: XFF'ye yalnız bağlantının gerçek adresi (peer) loopback ise (aynı makinedeki ters proxy) güven; değilse peer IP kullanılsın. Varsayılan davranış (ayar kapalı) değişmesin.
2. 📍 rs\app\src\yonetim.rs:252 civarı: LAN/QR adresi kalıcı tam yetkili API token'ını URL sorgusunda (`/m?k=TOKEN`) taşıyor.
   Çözüm: QR'a tek kullanımlık, kısa ömürlü (ör. 5 dk) bir eşleştirme kodu koy. Mobil sayfa bu kodu bir kez değiş-tokuş edip uzun ömürlü kimliği alsın: mevcut /pair akışını kullan (grep "pair" rs\crates\afudm-extras\src\h). URL'de kalıcı token kalmasın. Kod kullanılınca ya da süresi dolunca geçersiz olsun.
   Mevcut telefon kullanıcıları kırılmasın: eski `?k=` bağlantısıyla gelen istemci bir sürüm daha çalışsın ama sayfa onu hemen yeni akışa geçirsin ve adresten token'ı silsin (history.replaceState). Bu geçişi SONUC'ta açıkla.
3. 📍 rs\crates\afudm-api\src\listener.rs:254-256: çocuk süreç için boş port bağlanıp bırakılarak seçiliyor; aradaki kısa sürede başka bir yerel süreç portu alırsa token'lı istekler ona gidebilir.
   Çözüm: çocuk süreç dinleyiciyi kendisi açıp gerçek portu ebeveyne bildirsin (stdout/pipe). Ya da istek göndermeden önce karşı tarafın çocuk süreç olduğu doğrulansın (ör. çocuğa verilen tek seferlik nonce ile el sıkışma). Daha basit olanı seç, gerekçesini yaz.

## Kontrol (gerçek çıktıyı SONUC'a yapıştır)
- `cargo test --manifest-path rs\Cargo.toml` + `cargo clippy --manifest-path rs\Cargo.toml --all-targets -- -D warnings`
- `cargo test --manifest-path rs\app\Cargo.toml` + `cargo clippy --manifest-path rs\app\Cargo.toml --all-targets -- -D warnings`
- `cargo fmt --check` (iki workspace)
- `python -B rs\tests_hata\verify.py` ve `python -B rs\tests_hata\hepsi.py --only network`: GECTI
  (engine\aria2c.exe repo kökünde hazır)
SONUC: rs\docs\sonuc\SONUC_301A.md. Soru sorup durma.
