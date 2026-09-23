# AfuTube yt-dlp wrapper sürüm kararı

Tarih: 2026-09-23

## Denenen sürümler

- `0.17.4`: `io.github.junkfood02.youtubedl-android` koordinatlarıyla `test assembleDebug` başarılı.
- `0.18.1`: Aynı komut başarılı. Universal debug APK içinde `libqjs.so` arm64-v8a ve armeabi-v7a altında bulundu.

## Seçim

`0.18.1` seçildi. 0.17.4 derlenebilir ve daha düşük riskli geçiş adımı olarak doğrulandı; ancak 0.18.1 aynı API ile derleniyor ve YouTube JavaScript challenge akışı için QuickJS payload’ını (`libqjs.so`) içeriyor. Upstream 0.18.1 kaynak kodu `YoutubeDL.execute` içinde `--js-runtimes quickjs:...` ekliyor. Bu, gerçek cihazdaki YouTube analiz hatasının Python/yt-dlp çağrı zincirinde JavaScript challenge eksikliğiyle ilişkili olma ihtimaline karşı doğrudan fayda sağlıyor.

## Kanıt

- Upstream `0.17.4` ve `0.18.1` sürümlerinde `updateYoutubeDL(context, UpdateChannel)` API’si mevcut.
- Upstream 0.18.1 `YoutubeDL.init` içinde QuickJS native payload’ını hazırlıyor ve execute sırasında QuickJS runtime’ını yt-dlp’ye veriyor.
- Yerel CI-eşdeğeri: `gradle test assembleDebug --no-daemon --stacktrace` → `BUILD SUCCESSFUL`.
- APK kontrolü: `app-universal-debug.apk` → `lib/arm64-v8a/libqjs.so`, `lib/armeabi-v7a/libqjs.so`.

## Kaynaklar

- https://github.com/yausername/youtubedl-android/releases
- https://raw.githubusercontent.com/yausername/youtubedl-android/0.17.4/library/src/main/java/com/yausername/youtubedl_android/YoutubeDL.kt
- https://raw.githubusercontent.com/yausername/youtubedl-android/0.18.1/library/src/main/java/com/yausername/youtubedl_android/YoutubeDL.kt
