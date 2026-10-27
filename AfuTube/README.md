# AfuTube Android

The current Android distribution is the `github`/sideload flavor. Its in-app
APK updater and downloadable yt-dlp engine are intentionally not Play Store
features.

Before Google Play distribution, add separate `github` and `play` build
flavors. The `play` flavor must disable GitHub APK self-updates and external
executable-code downloads; the GitHub flavor may keep both behaviors.

Downloads and the player share files through WhatsApp, WhatsApp Business, or Android's share menu.
Settings text and APK sharing use the same flow and grant read access to shared files.

## Edit tab and third-party licenses

The Edit tab uses the WizardCut video editor (MIT) with FFmpegKitNext (LGPL-3.0-or-later).
Full license texts, the WizardCut NOTICE and the FFmpeg source offer are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and inside the APK under `assets/lisanslar/`.

Edit sekmesi WizardCut (MIT) ve FFmpegKitNext (LGPL) kullanır; lisans metinleri
THIRD_PARTY_NOTICES.md dosyasında ve APK içinde `assets/lisanslar/` altındadır.
