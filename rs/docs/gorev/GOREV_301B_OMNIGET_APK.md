# 3.0.1-B: OmniGet fikirleri + APK uyum denetimi (codex)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_301\rs\docs\EKIP_KURALLARI.md ve rs\docs\PLAN_RUST_TAURI.md satır 69-74 (OmniGet bölümü)
Çalışma dizini (worktree, dal feat/3.0.1): C:\Users\afuuu\Desktop\afuproject\AfuDM_301
DOKUNMA: C:\Users\afuuu\Desktop\afuproject\AfuDM ve AfuDM_rs klasörleri, kullanıcının AfuDM'i (6810/6811), data\. Pencere açma, emülatör açma.
Paralelde başka bir codex (3.0.1-A) rs\app\src\yonetim.rs, rs\crates\afudm-extras\src\h\, rs\crates\afudm-api\src\listener.rs ve mobil sayfa üzerinde çalışıyor; o dosyalara DOKUNMA.
YIKICI GIT YASAK: restore / checkout -- / reset / clean / stash / rebase / amend / push / switch / commit.
LİSANS: OmniGet GPL-3.0. Kodunu açma, kopyalama, uyarlama yok. Yalnız aşağıdaki fikirleri kendi kodumuzla yaz.

## ÇALIŞACAĞIN DOSYALAR
- rs\crates\afudm-core\src\queue.rs ve rs\crates\afudm-core\src\queue\ alt modülleri (sync_aria2, tamamlandi, hata işleme)
- JSON durum dosyası okuyan modüller (madde 3'te grep ile bul; bulduklarını SONUC'ta listele)
- ilgili test dosyaları, rs\docs\sonuc\SONUC_301B.md
- AfuTube\ ve AfuDM_Mobile\: YALNIZ OKU (madde 4)
Başka dosya gerekiyorsa dur ve SONUC'ta sor. Her maddeye birim testi ekle.

## Maddeler
1. 403 merdiveni. aria2 bir HTTP indirmesini 403 ile bitirirse, aynı adresi bir kez daha dene: tarayıcı benzeri başlıklarla (User-Agent, Accept, `Range: bytes=0-`, `Sec-Fetch-Mode: navigate`, `Sec-Fetch-Dest: document` vb.), aynı dir/out ile, kayıtlı çerez ve başlıkları koruyarak.
   - Yalnız bir kez dene; ikinci 403'te normal hata.
   - Hata kodunu aria2 tellStatus `errorCode`/`errorMessage` alanından tanı: 403 için aria2 errorCode 22 ve mesajda "403" geçer. Gerçek koşulu testle doğrula.
   - Yeniden deneme olayı log'a yazılsın.
2. Hata sayfası kontrolü. HTTP indirmesi tamamlanınca dosyanın ilk 512 baytına bak.
   - Dosya HTML ise (`<!doctype html`, `<html`, `<head` başları; baştaki boşluk/BOM atlanır) ve beklenen tür HTML değilse (uzantı .htm/.html değil, Content-Type text/html istenmemiş), indirmeyi "hata" say. Kullanıcıya tek cümle mesaj göster: "Sunucu dosya yerine bir hata sayfası gönderdi. Bağlantıyı tarayıcıda açıp yeniden dene."
   - Dosyayı silme, adını değiştirme. Tamamlandı kancaları (otomasyon) çalışmasın.
   - Kısa (<512 B) dosyalar da kontrol edilsin.
3. Bozuk durum dosyası karantinası. Uygulamanın okuduğu JSON durum/ayar dosyalarını bul (`grep -rn "serde_json::from_str\|from_slice\|from_reader" rs\crates rs\app\src`; DB değil, diskteki .json dosyaları).
   - Böyle bir dosya ayrıştırılamazsa `<ad>.corrupt-<YYYYmmdd-HHMMSS>` adıyla yanına taşınsın, log'a yazılsın, varsayılan değerle devam edilsin.
   - Var olan "sessizce varsayılan" davranışın yerine geçsin; uygulama çökmesin.
4. APK uyum denetimi (YALNIZ OKU + rapor). Kullanıcının sorusu: "APK'da yapılması gereken güncelleme var mı?"
   - AfuTube\ (Kotlin, Android) ve AfuDM_Mobile\ (Expo) masaüstü AfuDM'in HTTP API'sine bağlanıyor mu? `grep -rn "6811\|X-AfuDM-Token\|/pair\|/snapshot\|/add\b\|share_create\|/dosya" AfuTube AfuDM_Mobile --include=*.kt --include=*.ts --include=*.tsx --include=*.java`
   - Bağlanıyorsa: her çağrıyı Rust 3.0 karşılığıyla (rs\crates\afudm-api, rs\crates\afudm-extras\src\h) karşılaştır. 3.0.1-A'daki QR/eşleştirme değişikliğinden etkilenen var mı, yaz.
   - Bağlanmıyorsa açıkça "APK tarafında 3.0 için zorunlu güncelleme yok" yaz.
   - Ayrıca açık PR #90 (feat/afutube-klasor, 29 Eylül): `git log --oneline origin/main..origin/feat/afutube-klasor` ve `git diff --stat origin/main...origin/feat/afutube-klasor` ile ne içerdiğini, main ile çakışıp çakışmadığını (`git merge-tree`) özetle. Birleştirme YAPMA.

## Kontrol (gerçek çıktıyı SONUC'a yapıştır)
- `cargo test --manifest-path rs\Cargo.toml` + `cargo clippy --manifest-path rs\Cargo.toml --all-targets -- -D warnings` + `cargo fmt --manifest-path rs\Cargo.toml --all -- --check`
- `cargo test --manifest-path rs\app\Cargo.toml`
- `python -B rs\tests_hata\verify.py`, ardından `python -B rs\tests_hata\hepsi.py --only crash` (engine\aria2c.exe repo kökünde hazır)
SONUC: rs\docs\sonuc\SONUC_301B.md. Soru sorup durma.
