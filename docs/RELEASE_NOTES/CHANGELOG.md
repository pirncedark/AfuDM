# Changelog

## [3.1.0](https://github.com/pirncedark/AfuDM/compare/v3.0.1...v3.1.0) (2026-10-18)


### Features

* **afutube:** save downloads to visible AfuTube folder with open/share actions ([#90](https://github.com/pirncedark/AfuDM/issues/90)) ([157850a](https://github.com/pirncedark/AfuDM/commit/157850aaacf52a1c6c80409cd31a0f7b26bb68ae))
* upload speed limit setting (default 100 KB/s) ([#127](https://github.com/pirncedark/AfuDM/issues/127)) ([0b198a1](https://github.com/pirncedark/AfuDM/commit/0b198a11f2368a30c7719d3bf7cfb97b2bcf9315))

## [3.0.1](https://github.com/pirncedark/AfuDM/compare/v3.0.0...v3.0.1) (2026-10-18)


### Bug Fixes

* 3.0.1 security hardening and download reliability ([#124](https://github.com/pirncedark/AfuDM/issues/124)) ([9f9e334](https://github.com/pirncedark/AfuDM/commit/9f9e33473519c91a8ef97b0cf2b37e8c012e92d8))

## [3.0.0](https://github.com/pirncedark/AfuDM/compare/v2.9.9...v3.0.0) (2026-10-18)


### Features

* AfuDM 3.0 — Rust + Tauri rewrite ([#122](https://github.com/pirncedark/AfuDM/issues/122)) ([a451bc0](https://github.com/pirncedark/AfuDM/commit/a451bc0a9b2d46a3f5515bd23a7a3c960db90cf0))

## [2.9.9](https://github.com/pirncedark/AfuDM/compare/v2.9.8...v2.9.9) (2026-10-18)


### Bug Fixes

* **afutube:** download Instagram highlight stories ([#119](https://github.com/pirncedark/AfuDM/issues/119)) ([22e5184](https://github.com/pirncedark/AfuDM/commit/22e51847dea8b5fc717b53a56063de6600a3b123))
* **extension:** retry failed handoffs in browser context via add_blob so every download lands in AfuDM ([#121](https://github.com/pirncedark/AfuDM/issues/121)) ([fad47ff](https://github.com/pirncedark/AfuDM/commit/fad47ff06edb8e1cf7c037be3ec135d6a999082c))

## [2.9.8](https://github.com/pirncedark/AfuDM/compare/v2.9.7...v2.9.8) (2026-10-17)


### Bug Fixes

* **extension:** leave file:// downloads to the browser ([#117](https://github.com/pirncedark/AfuDM/issues/117)) ([477c91a](https://github.com/pirncedark/AfuDM/commit/477c91a84ad0e347d3cd159dd8cb658da821a577))

## [2.9.7](https://github.com/pirncedark/AfuDM/compare/v2.9.6...v2.9.7) (2026-10-17)


### Bug Fixes

* **torrent:** show re-added torrents and keep progress across restarts ([#115](https://github.com/pirncedark/AfuDM/issues/115)) ([6ee38be](https://github.com/pirncedark/AfuDM/commit/6ee38be74917aa34d783ddadf95804f584936f04))

## [2.9.6](https://github.com/pirncedark/AfuDM/compare/v2.9.5...v2.9.6) (2026-10-13)


### Bug Fixes

* **extension:** ignore download attribute on cross-origin links ([#111](https://github.com/pirncedark/AfuDM/issues/111)) ([c9b4eec](https://github.com/pirncedark/AfuDM/commit/c9b4eec6bb4dd7bd0266e4face8586d9dd9adcd8))

## [2.9.5](https://github.com/pirncedark/AfuDM/compare/v2.9.4...v2.9.5) (2026-10-13)


### Bug Fixes

* **integrity:** stop false 'damaged block' alarms; update button no longer stuck on hidden approvals ([#109](https://github.com/pirncedark/AfuDM/issues/109)) ([61df810](https://github.com/pirncedark/AfuDM/commit/61df810034de5c8d6a6048e67ed734387c6ce008))

## [2.9.4](https://github.com/pirncedark/AfuDM/compare/v2.9.3...v2.9.4) (2026-10-13)


### Bug Fixes

* **manager:** retry restarts the same row without leaving a ghost error row ([#107](https://github.com/pirncedark/AfuDM/issues/107)) ([98c906c](https://github.com/pirncedark/AfuDM/commit/98c906c5fe2ed32d988c71c6238c89651fd1cb3e))

## [2.9.3](https://github.com/pirncedark/AfuDM/compare/v2.9.2...v2.9.3) (2026-10-12)


### Bug Fixes

* **extension:** do not hijack generic /download/&lt;id&gt; landing pages ([#106](https://github.com/pirncedark/AfuDM/issues/106)) ([56e9818](https://github.com/pirncedark/AfuDM/commit/56e98189b1769027c53d5a2a22e7d559f6333507))
* **extension:** hand off ChatGPT/blob/small downloads to AfuDM + auto-accept default ([#105](https://github.com/pirncedark/AfuDM/issues/105)) ([7854e22](https://github.com/pirncedark/AfuDM/commit/7854e22802e9b418492b98b1f2bf1601d01d608e))

## [2.9.1](https://github.com/pirncedark/AfuDM/compare/v2.9.0...v2.9.1) (2026-09-30)


### Bug Fixes

* **api:** start local API without reverse DNS and keep native objects out of the download window bridge ([#96](https://github.com/pirncedark/AfuDM/issues/96)) ([f7a8c73](https://github.com/pirncedark/AfuDM/commit/f7a8c736ea715f800705a1a8db6265a31d579d7b))

## [2.9.0](https://github.com/pirncedark/AfuDM/compare/v2.8.0...v2.9.0) (2026-09-30)


### Features

* **afutube:** indirmelere klasoru acma ve paylasma ([#84](https://github.com/pirncedark/AfuDM/issues/84)) ([f7997ae](https://github.com/pirncedark/AfuDM/commit/f7997aeeebd2268d36db3e946d6680a4d4e87767))


### Bug Fixes

* **afutube:** bug report fixes (v1.6.1) ([#86](https://github.com/pirncedark/AfuDM/issues/86)) ([1969a3a](https://github.com/pirncedark/AfuDM/commit/1969a3a17028fb7574d9de48c720cffbe91a9151))
* **afutube:** portrait video quality and daily update check ([#89](https://github.com/pirncedark/AfuDM/issues/89)) ([03d49dd](https://github.com/pirncedark/AfuDM/commit/03d49dda09d2484271c8f0bdaba8b7bfac8e78ed))
* **ci:** run new download tests without PyInstaller, pywebview or aria2c ([#92](https://github.com/pirncedark/AfuDM/issues/92)) ([64596f0](https://github.com/pirncedark/AfuDM/commit/64596f029881d6403e8e5c25805fe74bf618f03f))
* **extension:** browser downloads open only the download window, no double downloads ([#91](https://github.com/pirncedark/AfuDM/issues/91)) ([94fb3da](https://github.com/pirncedark/AfuDM/commit/94fb3da457efaa08ac7d80134a08ca1eb4624b66))
* **extension:** say "pick the folder" instead of "queued" while AfuDM waits ([#88](https://github.com/pirncedark/AfuDM/issues/88)) ([33da9d1](https://github.com/pirncedark/AfuDM/commit/33da9d153c50f67ee30be738b82d11bd9ce33d5c))
* never return null errorMessage, tolerate pausing finished GIDs, repair live tests ([#87](https://github.com/pirncedark/AfuDM/issues/87)) ([450087a](https://github.com/pirncedark/AfuDM/commit/450087a9b8dbb39513356674010f8a2caa31fc04))

## [2.8.0](https://github.com/pirncedark/AfuDM/compare/v2.7.4...v2.8.0) (2026-09-28)


### Features

* **afutube:** share via WhatsApp, WhatsApp Business or share sheet ([#83](https://github.com/pirncedark/AfuDM/issues/83)) ([2dbd172](https://github.com/pirncedark/AfuDM/commit/2dbd17291e25e22c8f6c58467eea993b0ff97e29))
* in-app update from GitHub releases ([#82](https://github.com/pirncedark/AfuDM/issues/82)) ([23f1ca2](https://github.com/pirncedark/AfuDM/commit/23f1ca2110a22631d4ef1500ab4a78b88f9b2138))


### Bug Fixes

* **release:** align release-please with v-prefixed tags and core/surum.py ([#70](https://github.com/pirncedark/AfuDM/issues/70)) ([b564818](https://github.com/pirncedark/AfuDM/commit/b564818181f84b3946aa82812b50b38e8308879c))
