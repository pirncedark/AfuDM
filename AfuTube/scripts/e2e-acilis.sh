#!/usr/bin/env bash
# AfuTube acilis duman testi (CI emulatoru): AG KAPALIYKEN uygulama acilip ana ekrani gostermeli.
# v1.1.0 hatasi: acilis yt-dlp ag guncellemesini bekliyordu ve "Motor hazirlaniyor" ekraninda takiliyordu.
set -u
APK="$1"
PKG=com.afudm.afutube
OUT=e2e-out
LIMIT_SN=300
mkdir -p "$OUT"

adb install -r "$APK" || { echo "HATA: APK kurulamadi"; exit 1; }
adb shell svc wifi disable
adb shell svc data disable
adb logcat -c
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null

ok=0
start=$(date +%s)
while [ $(( $(date +%s) - start )) -lt $LIMIT_SN ]; do
  sleep 3
  adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1
  adb shell cat /sdcard/ui.xml > "$OUT/ui.xml" 2>/dev/null
  if grep -q 'Ana Ekran' "$OUT/ui.xml"; then ok=1; break; fi
done
sure=$(( $(date +%s) - start ))

adb exec-out screencap -p > "$OUT/ekran.png"
adb logcat -d > "$OUT/logcat.txt"
echo "--- logcat (hata/motor) ---"
adb shell ps -A -o PID,STAT,WCHAN,TIME,NAME | grep -E "afutube|python|ffmpeg|aria2" || true
grep -E "FATAL EXCEPTION|AndroidRuntime|AfuTubeMediaRuntime" "$OUT/logcat.txt" | head -40

if [ "$ok" != 1 ]; then
  echo "HATA: ag kapaliyken ana ekran ${LIMIT_SN} sn icinde gelmedi (ekran: $OUT/ekran.png)"
  exit 1
fi
adb shell pidof "$PKG" >/dev/null || { echo "HATA: ana ekrandan sonra uygulama kapandi"; exit 1; }
echo "BASARILI: ag kapaliyken ana ekran ${sure} sn icinde acildi"
