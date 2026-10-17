# Ekip H: Paylaşım, tünel, SMB, mobil eşleme (claude kod ajanı)
Önce oku: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\EKIP_KURALLARI.md
Çalışma dizini: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs
Python kaynağı (YALNIZ OKU): P = C:\Users\afuuu\Desktop\afuproject\AfuDM

## ÇALIŞACAĞIN DOSYALAR
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-extras\src\h\ (mod.rs ve alt dosyalar)
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\crates\afudm-extras\Cargo.toml: yalnız [dependencies] sonuna satır ekle
- C:\Users\afuuu\Desktop\afuproject\AfuDM_rs\rs\docs\sonuc\SONUC_H.md
DOKUNMA: extras\src\lib.rs, g1\, g2\, afudm-core, afudm-api.

## Python kaynağı
📍 P\core\paylasim_sunucusu.py (140): dosya paylaşım bağlantısı. Rotalar /share_create, /s/<kod>.
📍 P\core\tunel.py (160): cloudflared ile dışarıdan erişim. Motor yolu afudm-engine `engines::yol(app_dir, "cloudflared")`. Süreç penceresiz açılsın.
📍 P\core\smb_paylasim.py (51): ağ paylaşımı.
📍 Mobil eşleme: /pair ve /m (mobil arayüz). İlgili rotalar P\api\server.py ve P\api\web.py içinde; mobile_devices tablosu (store.query / execute).
   - Telefon arayüzü dosyaları: P\ui\mobil.html, panel.html, sw.js, manifest.webmanifest. Bunları app_dir\ui'den sun.
   - app.py start_pairing (425), Api.peers.
📍 Testler: P\tests\kopru_esleme_test.py, pair_loopback_test.py, paylasim_test.py, paylasim_link_test.py, smb_paylasim_test.py, tunel_test.py, telefona_indir_test.py, pwa_test.py, v175_mobil_test.py.
HTTP rotaları h::router(ctx) içinde olsun; yanıt biçimi P\api\server.py ile birebir. Eşleme kodu, token hash'i ve iptal kuralları aynı kalsın.

## Bitiş
- `cargo test -p afudm-extras` ve clippy (-D warnings) çıktısı SONUC'ta olsun.
- Gerçek tünel açma (cloudflared) testi YAPMA; sahte süreçle test et.
