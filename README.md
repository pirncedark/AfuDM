<h1 align="center">AfuDM</h1>

<p align="center">
  <img src="docs/readme/hero.svg" width="960" alt="AfuDM — files, videos and torrents. One portable Windows app." />
</p>
<p align="center">
  <a href="https://github.com/pirncedark/AfuDM/releases/latest"><img src="https://img.shields.io/badge/Download-latest_release-5b9dff?style=for-the-badge" alt="Download the latest Windows release" /></a>
</p>
<p align="center">
  <img src="https://img.shields.io/badge/Windows-64--bit-5b9dff" alt="Windows 64-bit" />
  <img src="https://img.shields.io/badge/Built_with-Rust_%2B_Tauri-a78bfa" alt="Built with Rust and Tauri" />
  <img src="https://img.shields.io/badge/Source-open-46c98b" alt="Open source" />
  <img src="https://img.shields.io/badge/Updates-automatic-46c98b" alt="Automatic updates" />
</p>

**Download once. Let AfuDM handle the rest.** Files, videos and torrents share one queue, with browser capture, download checks and optional actions when a file finishes. Free to use, open source and ad-free.

Since **3.0**, the desktop app is built with **Rust + Tauri**. Extract the release ZIP and launch `AfuDM.exe`; keep its companion folders together. The portable package includes aria2 and the browser extension. Video engines are optional.

[Quick start](#quick-start) · [How it works](#how-it-works) · [Why AfuDM](#why-afudm) · [Build from source](#build-from-source) · [Türkçe](#türkçe)

## How it works

<img src="docs/readme/how-it-works.svg" width="960" alt="Browser extension captures a link; AfuDM queues it; aria2 downloads file parts in parallel; download checks run; the file is saved and configured automation runs." />

1. **Click a download in your browser.** The extension hands it to AfuDM. If a handoff fails, a second path can fetch the file in the browser context and pass it to AfuDM.
2. **Watch the parts fill up.** aria2 downloads file segments over multiple connections. Pause and resume supported downloads from the same queue.
3. **Check what arrived.** AfuDM detects HTML error pages masquerading as files. SHA-256 verification is available when you supply an expected checksum; it is not a malware scan.
4. **Finish in the right folder.** Optional automation can extract ZIP archives, move files and notify you. Configure these actions once when you need them.

**On your phone:** scan AfuDM's pairing QR code on the same local network to manage downloads and transfer completed files. [AfuTube](AfuTube/README.md) is the separate Android video companion.

## Built for everyday downloads

<img src="docs/readme/features.svg" width="960" alt="Feature cards: parallel downloads, pause and resume, torrents, optional video engines, browser capture and fallback, one retry after HTTP 403, error-page detection, automatic updates, portability, phone QR pairing, idle engine sleep, English and Turkish." />

- **Files, torrents and video:** multi-connection downloads, magnet links and `.torrent` files in one app. Video sites use optional **yt-dlp**; support depends on the site and available engines. If yt-dlp or FFmpeg is missing, AfuDM downloads it automatically in the background on first launch — nothing to set up.
- **Recovery that knows the browser:** eligible HTTP 403 failures get one retry with browser-style headers. The extension also has a browser-context fallback; protected or expired links can still require a fresh link or sign-in.
- **Quiet when idle:** the aria2 engine saves its session and stops when no downloads need it, waking for new work.
- **Portable, with familiar controls:** no AfuDM installer, automatic updates, phone pairing and English/Turkish UI. Optional Windows integration may register file associations or startup behavior.

## Why AfuDM

<img src="docs/readme/why-afudm.svg" width="960" alt="Nine-row comparison: AfuDM combines free open source, portability, torrents, video, auto-update, error-page detection, a 403 retry, local QR pairing and no ads. Crosses mark sourced absences; dashes mean not verified." />

Choose AfuDM if you want **a portable, open-source app that combines downloads, torrents, browser recovery and local phone pairing**. Other managers share many of these features; this is a feature comparison, not a speed benchmark.

| Capability | AfuDM | IDM | Free Download Manager (current) | JDownloader 2 | Browser alone |
|:--|:--:|:--:|:--:|:--:|:--:|
| Free / open source | ✓ / ✓ | ✗ / ✗ | ✓ / — | ✓ / ✓ | Varies |
| Portable; no app installer | ✓ | — | — | ✓¹ | Varies |
| Torrent / magnet downloads | ✓ | ✗ | ✓ | — | — |
| Video-site downloads | ✓² | ✓ | ✓² | ✓² | Direct files only |
| Auto-update | ✓ | ✓ | — | ✓ | Varies |
| Detects error pages saved as files | ✓ | — | — | — | — |
| Retries 403 with browser headers | ✓³ | — | — | — | — |
| Local QR phone pairing | ✓ | — | —⁴ | — | — |
| No ads | ✓ | ✓ | ✓ | — | Varies |

**Legend:** ✓ = supported; ✗ = not supported; **— = not verified**. Error-page detection means HTML returned in place of an expected file. Auto-update may require confirmation in other apps. “Browser alone” means its built-in downloader without extensions; behavior varies by browser. Comparison checked on 2026-10-18.

¹ JDownloader's portable route requires Java. ² Site/engine/add-on dependent; no promise of every site. ³ One retry for eligible HTTP file downloads; access is not guaranteed. ⁴ FDM offers Android remote control with FDM installed on both devices; this table's row specifically means local **QR pairing**.

Sources: [IDM features](https://www.internetdownloadmanager.com/features2.html), [IDM trial terms](https://www.internetdownloadmanager.com/register/new_faq/purchase6.html), [IDM licence terms](https://www.internetdownloadmanager.com/support/terms-and-conditions.html), [IDM torrent FAQ](https://www.internetdownloadmanager.com/register/new_faq/functions4.html), [FDM features](https://www.freedownloadmanager.org/features.htm) (its open-source and portable claims are listed under legacy 3.9), [JDownloader](https://jdownloader.org/), [JDownloader portable setup](https://support.jdownloader.org/en/knowledgebase/article/portable-jdownloader-version), [JDownloader updates](https://support.jdownloader.org/en/knowledgebase/article/updates-update-behavior).

## Quick start

1. **↓ Download** the Windows ZIP from [Latest release](https://github.com/pirncedark/AfuDM/releases/latest).
2. **▣ Extract** the entire ZIP into a writable folder. Keep `AfuDM.exe`, `engine/` and `extension/` together.
3. **▶ Open `AfuDM.exe`** and add your first link.
4. **↗ Choose “Add to Chrome”** in AfuDM to enable browser capture. Follow the built-in guide; the extension connects to AfuDM during setup.

The Tauri interface uses Microsoft Edge WebView2. If Windows reports it missing, install the [official WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) and reopen AfuDM.

## Build from source

On Windows, install the stable [Rust toolchain](https://www.rust-lang.org/tools/install), Microsoft C++ Build Tools and WebView2 using the [Tauri Windows prerequisites](https://v2.tauri.app/start/prerequisites/#windows).

From the repository root:

```powershell
cd rs/app
cargo build --release --locked
```

The desktop binary is `rs/app/target/release/AfuDM.exe`. For a runnable folder, place `engine/aria2c.exe` and `extension/` beside the executable; these are supplied by the release ZIP. The UI is embedded in the executable. See the [Rust release packaging script](scripts/build_release_rust.ps1) for the package layout and the [changelog](docs/RELEASE_NOTES/CHANGELOG.md) for release history.

## Türkçe

**AfuDM: dosya, video ve torrent için taşınabilir Windows indirme yöneticisi.** Ücretsiz, açık kaynaklı ve reklamsızdır. 3.0'dan beri masaüstü uygulaması Rust + Tauri kullanır.

1. **Başlangıç:** [Son sürümü indir](https://github.com/pirncedark/AfuDM/releases/latest), ZIP'in tamamını çıkar ve `AfuDM.exe` dosyasını aç. Tarayıcıdan devralmak için **Chrome'a ekle** adımını izle.
2. **Nasıl çalışır:** eklenti bağlantıyı yakalar, aria2 parçaları paralel indirir, hata sayfası denetlenir. Beklenen SHA-256 verilirse sağlama kontrolü yapılır. İsteğe bağlı ZIP çıkarma, taşıma ve bildirim adımları çalışır.
3. **Özellikler:** duraklat/sürdür, torrent/magnet, video (yt-dlp ve FFmpeg eksikse ilk açılışta arka planda kendiliğinden iner, kurulum gerekmez), tarayıcı üzerinden ikinci indirme yolu, uygun 403 hatalarında bir yeniden deneme, otomatik güncelleme, boşta motorun uyuması ve Türkçe/İngilizce arayüz. Aynı yerel ağda QR ile telefon eşleştirme; ayrı Android uygulaması [AfuTube](AfuTube/README.md).
4. **Neden AfuDM:** taşınabilirlik, açık kaynak, torrent ve telefon eşleştirme aynı uygulamada. Yukarıdaki tabloda **✗** resmî kaynakla doğrulanan eksikliği gösterir; **—**, özelliğin olmadığı değil, burada doğrulanmadığı anlamına gelir. Ölçülmemiş hız/RAM üstünlüğü iddiası yoktur.
5. **Kaynaktan derleme:** Windows'ta Rust, C++ Build Tools ve WebView2 hazırken `rs/app` içinde `cargo build --release --locked` çalıştır. Çalıştırılabilir paket için `engine/` ve `extension/` klasörlerini koru.
