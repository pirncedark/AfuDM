# AfuTube third-party notices

AfuTube's **Edit** tab is powered by WizardCut. The full notice texts below are also
shipped inside the APK under `assets/lisanslar/` (not shown in the app UI).

## WizardCut — MIT License

Source: https://github.com/BigWizard94/wizardcut (v3.81.0, BigWizard Media; fork of
ClearCut by SysAdminDoc). Vendored in `feature/wizardcut/` with its original package
name `info.bigwizardmedia.wizardcut`.

```text
MIT License

Copyright (c) 2026 SysAdminDoc

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## WizardCut NOTICE

```text
ClearCut third-party notices

FFmpegKitNext / FFmpeg

ClearCut bundles a source-pinned LGPL-3.0-or-later build of FFmpegKitNext 8.1.0 with FFmpeg 8.1.2, OpenH264, libass, and the supporting libraries recorded in third_party/ffmpeg-kit-next/native-lock.json. The exact upstream commit is 3e223118e6e8fb6208693ecf3952e77cd096f587 and the reproducible build command is ./nix-android.sh -p android-r27d --enable-libass --enable-libjxl --enable-android-media-codec --enable-android-zlib --enable-openh264 --jobs=8. The ClearCut security patch disables the VobSub, TDSC, MACE6, ADX/AAX, PNG/APNG, RASC, IAMF, and LCL/ZLIB components named in the lockfile's required advisory inventory.

The Android package includes the upstream license resources under res/raw/license*.txt and res/raw/source.txt, plus ClearCut's exact source recipe under res/raw/ffmpeg_kit_next_source_offer.txt. Keep those resources and the corresponding-source access available with redistributed builds.

DeepFilterNet

ClearCut may bundle io.github.kaleyravideo:android-deepfilternet:0.0.8 for on-device audio noise reduction. The Kaleyra Android AAR is licensed under Apache License 2.0 and is built on the upstream DeepFilterNet project, whose code and model weights are available under MIT or Apache License 2.0 at the user's option. Keep the relevant Apache/MIT notices with redistributed builds that include the DeepFilterNet native library and bundled model.
```

## FFmpegKitNext / FFmpeg — LGPL-3.0-or-later (source offer)

The vendored AAR is `feature/wizardcut/third_party/ffmpeg-kit-next/ffmpeg-kit-next-8.1.0.aar`
(SHA-256 pinned in `feature/wizardcut/build.gradle.kts`); native components are listed
in `feature/wizardcut/third_party/ffmpeg-kit-next/native-lock.json`.

```text
ClearCut bundles an LGPL-3.0-or-later build of FFmpegKitNext 8.1.0 with FFmpeg 8.1.2.

Exact corresponding source:
https://github.com/arthenica/ffmpeg-kit-next/tree/3e223118e6e8fb6208693ecf3952e77cd096f587

Reproduction command:
./nix-android.sh -p android-r27d --enable-libass --enable-libjxl --enable-android-media-codec --enable-android-zlib --enable-openh264 --jobs=8

Build inputs: Android NDK 27.3.13750724, Android API 24, OpenH264 2.3.1
commit 0a48f4d2e9be2abb4fb01b4c3be83cf44ce91a6e, libass 0.17.4 commit
bbb3c7f1570a4a021e52683f3fbdf74fe492ae84. The ClearCut security patch
at third_party/ffmpeg-kit-next/clearcut-security.patch disables the
advisory-covered native components; its checksum and every required CVE
record are in the native lock.

The source lock and artifact checksum are distributed alongside ClearCut at
third_party/ffmpeg-kit-next/native-lock.json.
```
