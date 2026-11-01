# Changelog

## [3.4.1](https://github.com/pirncedark/AfuDM/compare/v3.4.0...v3.4.1) (2026-11-01)


### Bug Fixes

* **windows:** keep the window responsive when opening torrents ([#153](https://github.com/pirncedark/AfuDM/issues/153)) ([cf2e782](https://github.com/pirncedark/AfuDM/commit/cf2e7828c5e6e09f5ac6b09a1828834c0ea531dc))
* **windows:** remove unit binding from torrent error log ([#155](https://github.com/pirncedark/AfuDM/issues/155)) ([7563fe3](https://github.com/pirncedark/AfuDM/commit/7563fe3c44633069a342da4973ffde871b2d66db))

## [3.4.0](https://github.com/pirncedark/AfuDM/compare/v3.3.0...v3.4.0) (2026-11-01)


### Features

* **afutube-editor:** 40% preview with height-first aspect, full-height thumbnails, separate text lane, tools start at Kes ([e192ff0](https://github.com/pirncedark/AfuDM/commit/e192ff021bf26b1b407878cf3e7a604950534e55))
* **afutube-editor:** add Cut, Text, Filter, Aspect tools to editor UI + screen e2e test ([280784d](https://github.com/pirncedark/AfuDM/commit/280784ded0a4964f219842bcf48723ee569ac8ec))
* **afutube-editor:** aspect-ratio preview, compact tool bar, outline handles, pixel_6 e2e ([ff41fa4](https://github.com/pirncedark/AfuDM/commit/ff41fa4c4ddb4fbb23629a4c581014d41ba32763))
* **afutube-editor:** clip selection, playhead split, music picker and track controls (WIP) ([ccd1af8](https://github.com/pirncedark/AfuDM/commit/ccd1af8f6145035bf2deca4b6db2982f030cf131))
* **afutube-editor:** real RMS music waveform and draggable text lane handles ([069047e](https://github.com/pirncedark/AfuDM/commit/069047e55e1f9049407e52982af57a73717c66e7))
* **afutube-editor:** stage 1 module skeleton, project model, undo stack ([33ce6e4](https://github.com/pirncedark/AfuDM/commit/33ce6e4a301a7d2dd69c2c409c252ecd56235797))
* **afutube-editor:** stage 2 composition builder, live preview, timeline ([7e17a24](https://github.com/pirncedark/AfuDM/commit/7e17a244fe0d6d1cbf6e1c3c982e692a12040036))
* **afutube-editor:** stage 3 speed, volume, fade, music track, ducking ([cff94f2](https://github.com/pirncedark/AfuDM/commit/cff94f2cc05b4fccd5c9521d1374c9d181c6f990))
* **afutube-editor:** stage 4 text overlay, filters, aspect ratio ([e5c991c](https://github.com/pirncedark/AfuDM/commit/e5c991c33e6e62f6f7b0bdbc95f361e2cb9f3af2))
* **afutube-editor:** stage 5 export worker, draft, first-run tip, extract audio ([113c2ca](https://github.com/pirncedark/AfuDM/commit/113c2cae6c535a69f10ceb1718f3d65e27c8e7b9))
* **afutube-editor:** stage 6 wire editor, remove old dialog, notices, e2e export test ([a42bc63](https://github.com/pirncedark/AfuDM/commit/a42bc63339ea38ca4c3819a449a739b652c8a9d4))
* **afutube:** adapt shared Edit components to HIG rules ([2e56dd1](https://github.com/pirncedark/AfuDM/commit/2e56dd1502b2ab841ad0a837e8554cd0657eccb5))
* **afutube:** add AfuTube-style primary button, card and advanced section ([94dc4be](https://github.com/pirncedark/AfuDM/commit/94dc4be9e98dee4843412d21d4ac6bd03eed9481))
* **afutube:** add WizardCut editor (MIT) as :feature:wizardcut library ([b78e244](https://github.com/pirncedark/AfuDM/commit/b78e2441924afed7a20094c246352796801dbab1))
* **afutube:** album cover art in the music tab ([811488f](https://github.com/pirncedark/AfuDM/commit/811488f6e58f759722f32c63b425121a865d19e2))
* **afutube:** anonymous daily active-user signal + settings counter ([93b7d91](https://github.com/pirncedark/AfuDM/commit/93b7d91b785e8ef1823918789f5619055ddfe5d6))
* **afutube:** auto edit panel keeps one generate action ([b09e1e7](https://github.com/pirncedark/AfuDM/commit/b09e1e756e33cd6f862f4cc2ead280fc5087fd93))
* **afutube:** caption panel has one Add captions action ([1c24e94](https://github.com/pirncedark/AfuDM/commit/1c24e94478aec58e33f0960d2cd23ad4fb1aeefa))
* **afutube:** delete files, trim videos and add music to a video ([26c21b7](https://github.com/pirncedark/AfuDM/commit/26c21b7538899aed13d7845409c2938849b4e761))
* **afutube:** Edit tab opens WizardCut; Downloads edit sends the video to WizardCut, old editor removed ([d118b4b](https://github.com/pirncedark/AfuDM/commit/d118b4b67875f4c6a77070a46e144a93a0900a24))
* **afutube:** editor bottom bar shows four tools and More ([a13fc7b](https://github.com/pirncedark/AfuDM/commit/a13fc7b2e062ec8c7b5c0bf8e35fec6b66d05dc4))
* **afutube:** editor settings show quality and save folder only ([8b9d2d1](https://github.com/pirncedark/AfuDM/commit/8b9d2d1f26ebe496b46cb761e192253dc10f81a8))
* **afutube:** export errors show one sentence and estimate only with a target size ([15fa9e8](https://github.com/pirncedark/AfuDM/commit/15fa9e8d22faefb4b0d1f5ba12c3048dbe92a05d))
* **afutube:** export sheet shows quality and one Save button ([5cdc47d](https://github.com/pirncedark/AfuDM/commit/5cdc47dff7f18dadc79092a8692292a22811b4ff))
* **afutube:** music player tab + torrent peer discovery fix ([#143](https://github.com/pirncedark/AfuDM/issues/143)) ([0bf1eb8](https://github.com/pirncedark/AfuDM/commit/0bf1eb86c92ba985f3e6f85b57f0cddfbdfa16cc))
* **afutube:** music seek/groups/covers, delete, trim, add music, recommended update ([4f641fd](https://github.com/pirncedark/AfuDM/commit/4f641fd545b8aec45f5d99ae74ff602d20ea3989))
* **afutube:** music tab — 10 s seek, progress bar, folder/album/artist groups, delete ([1248106](https://github.com/pirncedark/AfuDM/commit/1248106e955b4d56ad37978b569070a6b298258a))
* **afutube:** music view switch + full video editor (1.13.0) ([7a1a172](https://github.com/pirncedark/AfuDM/commit/7a1a1722004f809b2dfa143a075e2506358c0236))
* **afutube:** name the auto edit tab Otomatik düzenle ([1d8c836](https://github.com/pirncedark/AfuDM/commit/1d8c836277ba4bbd244baadcc2921b4f144ac8fd))
* **afutube:** open-source licenses card in Settings (WizardCut MIT, FFmpegKit LGPL source offer) ([f345d45](https://github.com/pirncedark/AfuDM/commit/f345d45ec3f22cfae9fa0c09605d848baad98a97))
* **afutube:** point the active-user counter at the live server ([652120f](https://github.com/pirncedark/AfuDM/commit/652120f0d50bc43e5c875e3175ff043a5abb0304))
* **afutube:** recommended update dialog with real changelog ([6369d7c](https://github.com/pirncedark/AfuDM/commit/6369d7ccc83cb82a2656619aedfb60b3ebe7a5ae))
* **afutube:** simpler project list and new project screen ([44f569e](https://github.com/pirncedark/AfuDM/commit/44f569e4789471c47c399ca5e17858b119577c45))
* **afutube:** simpler WizardCut wording, one-line errors ([7842310](https://github.com/pirncedark/AfuDM/commit/7842310b0b4483c547e96fd4d0ae9d3e6947d500))
* **afutube:** Topluluk card — anonymous active-user counter ([1c23e5f](https://github.com/pirncedark/AfuDM/commit/1c23e5f27f5672e4ce92da42d67ea97d73b021b2))
* **afutube:** Turkish translation for WizardCut (values-tr, 2942 strings + 82 plurals) ([2b3ba34](https://github.com/pirncedark/AfuDM/commit/2b3ba34a013679081d243a4a3276529a7743db11))
* **afutube:** WizardCut uses AfuTube colour tokens ([108e097](https://github.com/pirncedark/AfuDM/commit/108e0972ed62b399f65a919323c1911f6f72aef6))
* **afutube:** WizardCut uses AfuTube corner radius and typography ([d13df54](https://github.com/pirncedark/AfuDM/commit/d13df542f8216bf4b77207930eafe2f988a220f5))


### Bug Fixes

* **afutube-editor:** add core-ktx and fix share intent clipData chain ([a70be73](https://github.com/pirncedark/AfuDM/commit/a70be732120416fe34b3bbdcd8ececcfb8fee908))
* **afutube-editor:** add media3 deps to app androidTest classpath ([b2ed3b2](https://github.com/pirncedark/AfuDM/commit/b2ed3b26efc6db893df1f9bdefb8295b2b6967bb))
* **afutube-editor:** compile errors in text/music panels and zoom gesture ([3427128](https://github.com/pirncedark/AfuDM/commit/34271284e537b5062b5f635f820a1786bdf61cfe))
* **afutube-editor:** convert clip width Long to Int before dp ([d09b234](https://github.com/pirncedark/AfuDM/commit/d09b234ff8acc5295d5a3ea6636defd64a3c5877))
* **afutube-editor:** correct compose ui-test imports in screen e2e ([c48b325](https://github.com/pirncedark/AfuDM/commit/c48b3258cc4c9265d2697c446496771c15e35e31))
* **afutube-editor:** pass full source duration to EditedMediaItem so clipped segments are valid ([a09b083](https://github.com/pirncedark/AfuDM/commit/a09b08395b58aa8d2f20ec68814a29e9240ea4e3))
* **afutube-editor:** restore symbols lost in cp1254 round-trip (♪, │, −) ([337f0ec](https://github.com/pirncedark/AfuDM/commit/337f0ec1c1f07178ffdd7118a0b20b9b541fbbe4))
* **afutube-editor:** restore UTF-8 Turkish text, waveform decoder variable, unboxed PCM ([c87213e](https://github.com/pirncedark/AfuDM/commit/c87213e73cad2af75703fcd5456a555a290fe688))
* **afutube-editor:** set clip speed via EditedMediaItem.setSpeed for CompositionPlayer ([ea97e66](https://github.com/pirncedark/AfuDM/commit/ea97e66ccafe657eb0ec50bc5895e96fdd9ff8a1))
* **afutube-editor:** split pure CompositionPlan from Media3 converter ([0446c73](https://github.com/pirncedark/AfuDM/commit/0446c73c475d734dca37451f3c4a9e97a37e8e28))
* **afutube-editor:** use experimental speed-changing effect so CompositionPlayer preview works ([86341a3](https://github.com/pirncedark/AfuDM/commit/86341a301df6d9c7e21d6fc4042941647c18e8b8))
* **afutube:** editor header shows only Edit ([57c3c63](https://github.com/pirncedark/AfuDM/commit/57c3c63590d0757aaf85d632453c656df50aa37d))
* **afutube:** Instagram sign-in button in Settings; login page no longer blank ([648cf42](https://github.com/pirncedark/AfuDM/commit/648cf420ff02eb043f7b1361ce6c231ca3948cac))
* **afutube:** Instagram sign-in button in Settings; login page no longer blank ([0640b84](https://github.com/pirncedark/AfuDM/commit/0640b84bd0aa3bb1cff5d51720cb85a4bdbe292e))
* **afutube:** localize WizardCut category and tag labels ([58133da](https://github.com/pirncedark/AfuDM/commit/58133dab07c8154245240be97c0440c3656e4118))
* **afutube:** move hardcoded WizardCut UI text to string resources ([51e8415](https://github.com/pirncedark/AfuDM/commit/51e8415516cb010f27c47e4a2168aa3f3eebb5bb))
* **afutube:** move license texts out of Settings into THIRD_PARTY_NOTICES.md and APK assets ([759cdec](https://github.com/pirncedark/AfuDM/commit/759cdecf14dd465f2e7344a1c8210b78498fad58))
* **afutube:** show AfuTube branding in the Edit tab ([726eae2](https://github.com/pirncedark/AfuDM/commit/726eae2a779120598d6a8b850a65bbbb0e4a58c4))
* **afutube:** start WizardCut services lazily on first Edit open ([b0ea52e](https://github.com/pirncedark/AfuDM/commit/b0ea52e3486b6b53525de185762568f806a672c2))
* **ci:** read AfuTube changelog from the annotated tag message ([c6a0219](https://github.com/pirncedark/AfuDM/commit/c6a0219c19a5753556c453de0821f5c17fcce0f1))
* **windows:** open dropped torrents and magnet links ([#151](https://github.com/pirncedark/AfuDM/issues/151)) ([009dffc](https://github.com/pirncedark/AfuDM/commit/009dffc862d49bbc37917736812a25e0f4c3444a))

## [3.3.0](https://github.com/pirncedark/AfuDM/compare/v3.2.0...v3.3.0) (2026-10-22)


### Features

* **afutube:** Instagram oturum destegi, giris diyalogu ve dinamik hata basligi ([#142](https://github.com/pirncedark/AfuDM/issues/142)) ([e6cc415](https://github.com/pirncedark/AfuDM/commit/e6cc415ae87138979804abe53d8092b11e3f9786))


### Bug Fixes

* single download dialog, no duplicate prompts, correct Folder button ([#140](https://github.com/pirncedark/AfuDM/issues/140)) ([b5b02b1](https://github.com/pirncedark/AfuDM/commit/b5b02b1cf42510ca3d710c867a7aef0adc844cf6))

## [3.2.0](https://github.com/pirncedark/AfuDM/compare/v3.1.1...v3.2.0) (2026-10-20)


### Features

* **afutube:** replay, repeat one/all and play folder as playlist ([#137](https://github.com/pirncedark/AfuDM/issues/137)) ([e99c390](https://github.com/pirncedark/AfuDM/commit/e99c390db6d83ef8e627ce8329d513daec77455d))


### Bug Fixes

* **ui:** show app version reliably on startup ([#139](https://github.com/pirncedark/AfuDM/issues/139)) ([d43dc66](https://github.com/pirncedark/AfuDM/commit/d43dc66d50be3b56be8da1934ab779316387e46b))

## [3.1.1](https://github.com/pirncedark/AfuDM/compare/v3.1.0...v3.1.1) (2026-10-19)


### Bug Fixes

* **ui:** show upload/sharing speed limit next to download limit with a clear label ([#135](https://github.com/pirncedark/AfuDM/issues/135)) ([3608fa8](https://github.com/pirncedark/AfuDM/commit/3608fa899efa3d514223481ceefa4ee73260c0e1))

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
