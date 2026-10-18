# R2: Yerel 3.0.0 paket provası + eski güncelleyici provası (codex)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md ve C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_R1.md
Repo kökü: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs (dal feat/rust-tauri)
DOKUNMA: C:\Users\afuuu\Desktop\afuproject\AfuDM (kullanıcının kopyası), oradaki data\, çalışan AfuDM.exe, portlar 6810/6811. Pencere açma.
YIKICI GIT YASAK: restore / checkout -- / reset / clean / stash / rebase / amend / push / switch / commit.
Not: Arka planda `python -B rs\tests_hata\hepsi.py` koşuyor olabilir; onu durdurma, rs\tests_hata\bin\ dosyalarına dokunma.

## ÇALIŞACAĞIN DOSYALAR
- core\surum.py: YALNIZ prova için geçici olarak 2.9.9 → 3.0.0 yap, prova bitince Edit ile tekrar 2.9.9'a çevir (git ile geri alma YASAK). Sonda `git diff --stat core/surum.py` boş olmalı.
- scripts\build_release_rust.ps1, scripts\verify_release.ps1, scripts\smoke_test.ps1: yalnız provada hata çıkarsa düzelt.
- build_out\ (prova çıktısı; varsa önceki prova klasörünü kendin oluşturduysan sil, başkasınınsa farklı ad kullan)
- rs\docs\sonuc\SONUC_R2.md
Başka dosya gerekiyorsa dur ve SONUC'ta sor.

## Yapılacaklar
1. engine\aria2c.exe repo kökünde hazır (indirildi). `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_release_rust.ps1 -Tag v3.0.0 -Offline` (ya da betiğin beklediği parametreler) → build_out\AfuDM-v3.0.0-win64.zip.
2. `scripts\verify_release.ps1 <zip> -PackageType Rust` ve `scripts\smoke_test.ps1 <zip> -PackageType Rust` → çıkış 0.
3. Eski güncelleyici provası: SONUC_T2.md bölüm 3'teki yöntemi (rs\tests_hata\upgrade.py) bu GERÇEK release zip'i ile tekrarla. Python 2.9.x güncelleyicisi (C:\Users\afuuu\Desktop\afuproject\AfuDM\core\guncelleme.py YALNIZ OKU / import) geçici klasörde, yerel sahte GitHub sunucusuyla bu zip'i indirip SHA doğrulasın, açsın, AfuDM.exe'yi değiştirsin; kullanıcı data\ korunmalı. upgrade.py zip yolu parametresi almıyorsa ona en fazla 20 satırlık parametre ekleyebilirsin (dosyayı listeye ekle ve SONUC'ta belirt).
4. Paketteki AfuDM.exe'nin ProductVersion=3.0.0 ve test-kapisi kodunu İÇERMEDİĞİNİ doğrula (ör. exe içinde "/_test/api_call" dizgisi aranır → bulunmamalı).
5. core\surum.py'yi 2.9.9'a geri çevir; `git status --short` çıktısını SONUC'a koy.

## Kontrol
Her adımın gerçek komut çıktısını SONUC_R2.md'ye yapıştır. Zip boyutu ve SHA-256 yaz. Soru sorup durma.
