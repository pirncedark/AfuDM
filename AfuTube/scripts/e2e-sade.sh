#!/usr/bin/env bash
set -u
PKG=com.afudm.afutube
OUT=e2e-out
UI="python3 AfuTube/scripts/ui.py"
mkdir -p "$OUT"
dump() { adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; adb shell cat /sdcard/ui.xml > "$OUT/$1.xml" 2>/dev/null; }
tap() { local xy; xy=$($UI "$@") || return 1; adb shell input tap $xy; }
chooser_front() { adb shell dumpsys activity activities | grep -iE 'chooser|intentresolver|ResolverActivity' >/dev/null; }
wait_chooser() {
  local seconds=$1; local t=0
  while [ "$t" -lt "$seconds" ]; do chooser_front && return 0; sleep 1; t=$((t+1)); done
  return 1
}
return_to_settings() {
  local dump_name=$1 back_count=0 second=0 focus=""
  # The chooser closes on BACK. Then wait up to six seconds for Settings to
  # redraw; MainActivity handles BACK by leaving the app.
  while [ "$back_count" -lt 3 ]; do
    focus=$(adb shell dumpsys window | grep -m1 'mCurrentFocus' || true)
    if printf '%s' "$focus" | grep -q "$PKG"; then
      # AfuTube is foreground already; only wait for its UI to redraw.
      for second in 1 2 3 4 5 6; do
        dump "$dump_name"
        grep -q 'text="APK ' "$OUT/$dump_name.xml" && return 0
        sleep 1
      done
      return 1
    fi

    # Only dismiss a chooser or another foreground app, never AfuTube.
    if chooser_front || ! printf '%s' "$focus" | grep -q "$PKG"; then
      adb shell input keyevent KEYCODE_BACK
      back_count=$((back_count+1))
    fi
    for second in 1 2 3 4 5 6; do
      dump "$dump_name"
      grep -q 'text="APK ' "$OUT/$dump_name.xml" && return 0
      sleep 1
    done
  done
  return 1
}
adb shell input keyevent KEYCODE_BACK
sleep 2
dump ayarlar
tap tap-text "$OUT/ayarlar.xml" "Ayarlar" || { echo "HATA: Ayarlar sekmesi yok"; exit 1; }
sleep 2; dump ayarlar
adb exec-out screencap -p > "$OUT/sade-ayarlar.png"
for text in "Güncellemeleri denetle" "Link gönder" "APK gönder"; do
  grep -q "text=\"$text\"" "$OUT/ayarlar.xml" || { echo "HATA: Ayarlar metni yok: $text"; exit 1; }
done
for forbidden in DRM Gavel aria2c; do
  grep -qi "$forbidden" "$OUT/ayarlar.xml" && { echo "HATA: Ayarlarda istenmeyen içerik: $forbidden"; exit 1; }
done
adb shell input swipe 160 510 160 180 400
sleep 1; dump ayarlar-alt
grep -q 'text="Yalnızca indirme hakkın olan içerikleri indir."' "$OUT/ayarlar-alt.xml" || { echo "HATA: Yumuşak alt uyarı yok"; exit 1; }
forbidden_found=0
for forbidden in DRM Gavel aria2c; do
  if grep -qi "$forbidden" "$OUT/ayarlar-alt.xml"; then echo "HATA: Ayarlarda istenmeyen içerik: $forbidden"; forbidden_found=1; fi
done
[ "$forbidden_found" = 0 ] || exit 1
adb shell input swipe 160 180 160 510 400
sleep 1; dump ayarlar
echo "BASARILI: ayarlar sade"

tap tap-text "$OUT/ayarlar.xml" "Link gönder" || { echo "HATA: Link gönder yok"; exit 1; }
wait_chooser 10 || { echo "HATA: link paylaşım seçicisi açılmadı"; exit 1; }
return_to_settings apk-paylas || { echo "HATA: paylasimdan sonra Ayarlar'a donulemedi"; exit 1; }
echo "BASARILI: link paylasimi acildi"
tap tap-text "$OUT/apk-paylas.xml" "APK gönder" || { echo "HATA: APK gönder yok"; exit 1; }
wait_chooser 20 || { echo "HATA: APK paylaşım seçicisi açılmadı"; adb logcat -d | grep -A20 'FATAL EXCEPTION' | tail -40; exit 1; }
return_to_settings apk-paylas-son || { echo "HATA: paylasimdan sonra Ayarlar'a donulemedi"; exit 1; }
adb shell pidof "$PKG" >/dev/null || { echo "HATA: APK paylaşımından sonra uygulama kapandı"; exit 1; }
echo "BASARILI: APK paylasimi acildi"
