# AfuTube Android

The current Android distribution is the `github`/sideload flavor. Its in-app
APK updater and downloadable yt-dlp engine are intentionally not Play Store
features.

Before Google Play distribution, add separate `github` and `play` build
flavors. The `play` flavor must disable GitHub APK self-updates and external
executable-code downloads; the GitHub flavor may keep both behaviors.

Downloads and the player share files through WhatsApp, WhatsApp Business, or Android's share menu.
Settings text and APK sharing use the same flow and grant read access to shared files.
