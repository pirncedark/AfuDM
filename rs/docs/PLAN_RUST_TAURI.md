# AfuDM 3.0: Rust + Tauri ile yeniden yazım planı (TASLAK, onay bekliyor)

## Hedef
- Boşta RAM: ~1,3 GB → ≤ 60 MB (pencere kapalı). Pencere açıkken ≤ 250 MB.
- Davranış aynı kalır: Chrome eklentisi, arayüz, API (127.0.0.1:6811 + token), veri klasörü (data\afudm.db), indirme motorları (aria2c, yt-dlp, ffmpeg, cloudflared).
- 2.9.x kullanıcıları otomatik güncellemeyle 3.0'a geçer; verileri kaybolmaz.

## Mevcut kod (ölçüldü)
- Python: 16.733 satır (manager.py 2708, app.py 2192, api/server.py 1195, eklenti.py 1112, ...).
- Arayüz: ui/ 9.525 satır HTML/JS. Rust'a geçmez, Tauri'de yeniden kullanılır.
- API: 38 uç nokta. Testler: tests/ altında 123 dosya.
- Araçlar hazır: cargo/rustc 1.98.1, node 24.

## Temel ilke: "sözleşme önce"
Yeni exe, eski Python testlerinin HTTP üzerinden çalışan kısmını aynen geçmek zorunda (kara kutu uyum testi).
Böylece "çalışıyor" iddiası kanıta dayanır.

## Çalışma yeri
- Yeni worktree: C:\Users\afuuu\Desktop\afuproject\AfuDM_rs (dal: feat/rust-tauri). Ana ağaca ve kullanıcının commitlenmemiş işine dokunulmaz.
- Cargo workspace: crates/afudm-db, crates/afudm-engine, crates/afudm-core, crates/afudm-api, crates/afudm-extras, app/ (Tauri).
- Her ajan YALNIZ kendi crate klasörüne yazar. Ortak tipler crates/afudm-types içindedir; bu crate'i yalnız Claude değiştirir.

## Dalgalar

### Dalga 0: iskelet + sözleşme (Claude, sıralı, ~1 sa)
- Workspace, afudm-types (Download, Settings, Snapshot, ControlAction, hata tipleri).
- docs/API_SOZLESME.md: 38 uç noktanın istek/yanıt şekli, api/server.py'den çıkarılır.
- DB şeması: mevcut SQLite tabloları aynen korunur (göç yok, aynı dosya açılır).
- Her ajan için görev dosyası; içinde ÇALIŞACAĞIN DOSYALAR, 📍 kaynak Python satırları ve yıkıcı git yasağı bulunur.

### Dalga 1: paralel yazım (6 ajan aynı anda, ~4–8 sa)
| Ekip | Ajan | Crate | Kaynak Python |
|---|---|---|---|
| A Motor | codex | afudm-engine | daemon.py, rpc.py, aria2.py, engines.py (aria2c başlat, JSON-RPC, yt-dlp/ffmpeg çağrısı) |
| B Veri | codex | afudm-db | db.py, models.py, settings_validation.py, paths.py, kaydet.py |
| C Çekirdek-1 | codex | afudm-core/queue | manager.py: ekle, kopya tespiti, kuyruk, snapshot, kontrol |
| D Çekirdek-2 | claude (kod ajanı) | afudm-core/torrent+video | manager.py torrent/seed/tracker/metrik + video mux, dosya_adi.py |
| E API | codex | afudm-api (axum) | api/server.py, api/web.py, erisim.py (token, CORS, 38 uç) |
| F Kabuk | claude (kod ajanı) | app/ (Tauri 2) | app.py, pencere.py, baslangic.py, servis.py, windows_integration.py, tepsi; ui/ köprüsü pywebview → Tauri invoke; boşta uyku |

### Dalga 2: paralel yazım 2 (~3–5 sa)
| G Ekler | codex | afudm-extras | guncelleme.py (GitHub oto güncelleme), cerez.py, eklenti.py, linkgrabber.py, butunluk.py, rules.py, automation.py |
| H Paylaşım | codex | afudm-extras/share | paylasim_sunucusu.py, tunel.py, smb_paylasim.py, mobil eşleme (/pair, /m) |

### Dalga 3: hata testi (paralel)
- OpenCode: eski Python HTTP testlerini Rust exe'ye karşı koşturur (uyum). Ayrıca Chrome eklenti testleri (.mjs) ve ui-gate Playwright.
- Codex: cargo test + clippy -D warnings, hatalı girdi testleri (/add bozuk URL, dev JSON, token yok), çökme/yeniden başlatma (ilerleme kaybolmuyor mu), 2.9.8 → 3.0 güncelleme provası.
- Ölçüm: boşta ve indirme sırasında RAM/CPU; 2.9.8 ile yan yana.
- Kalan hata → ilgili ekibe geri döner, düzeltilir, test tekrarlanır (döngü yeşile kadar).

### Dalga 4: Claude gözden geçirme
- /code-review + bağımsız inceleme. Gerçek indirme: HTTP dosyası, torrent, YouTube videosu, Chrome'dan PDF.
- Yalnız hepsi yeşilse: PR → CI → v3.0.0 sürümü → tüm kullanıcılara oto güncelleme.

## Kabul ölçütleri (hepsi kanıtla)
1. Python HTTP uyum testleri: %100 geçer (ya da her istisna yazılı gerekçeli).
2. cargo test + clippy temiz.
3. Boşta RAM ≤ 60 MB; indirme hızı 2.9.8'den düşük değil.
4. 2.9.8'den oto güncelleme sonrası eski indirmeler ve ayarlar duruyor.
5. Chrome eklentisi değişmeden çalışıyor.

## Riskler
- manager.py büyük ve birbirine bağlı (C ve D aynı mantığı paylaşır) → sınır afudm-types'ta net çizilir.
- Codex kotası: 17 Eki'de bitikti, bugün çalıştı. Biterse iş claude kod ajanına kayar.
- Oto güncelleme: 2.9.x güncelleyici zip içindeki AfuDM.exe'yi değiştiriyor; 3.0 zip düzeni aynı tutulmalı, yoksa kullanıcılar takılır.
- Sürüm 3.0 yayınlanana kadar 2.9.8 kullanılmaya devam eder (risk yok).

## Sonraki sürüm (kullanıcı kararı, 18 Eki: seçenek 1)
OmniGet incelemesinden alınan fikirler. OmniGet GPL-3.0 lisanslı; kod kopyalanmayacak, aynı fikirler kendi kodumuzla yazılacak.
Uyum testinde kritik fark 0 olduktan sonra, 3.0.1 sürümünde:
1. 403 merdiveni: 403 alınınca aynı adresi tarayıcı benzeri başlıklarla (Range bytes=0-, sec-fetch-*) bir kez daha dene.
2. Hata sayfası kontrolü: indirme bitince dosyanın ilk 512 baytına bak; HTML hata sayfasıysa indirmeyi hata say.
3. Bozuk durum dosyası karantinası: JSON durum dosyası okunamazsa dosyayı .corrupt-<zaman> adıyla sakla, log yaz, sonra varsayılanı kullan.
Daha sonra: host başına uyarlanır bağlantı sayısı (yavaş artır, hızlı düşür) ve genel bağlantı bütçesi (~24).
