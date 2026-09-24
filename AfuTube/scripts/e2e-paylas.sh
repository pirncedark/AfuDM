#!/usr/bin/env bash
# AfuTube share intent smoke test: warm navigation, one-shot result, and cold start.
set -u
PKG=com.afudm.afutube
OUT=e2e-out
URL="https://www.w3schools.com/html/mov_bbb.mp4"
UI="python3 AfuTube/scripts/ui.py"
mkdir -p "$OUT"

dump() { adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; adb shell cat /sdcard/ui.xml > "$OUT/$1.xml" 2>/dev/null; }
bitir() { adb exec-out screencap -p > "$OUT/paylas-$1.png"; adb logcat -d > "$OUT/logcat-paylas.txt"; grep -A25 "FATAL EXCEPTION" "$OUT/logcat-paylas.txt" | head -60; }
cokme_var() { adb logcat -d | grep -q "FATAL EXCEPTION" || ! adb shell pidof "$PKG" >/dev/null; }
tap() { local xy; xy=$($UI "$@") || return 1; adb shell input tap $xy; }
guncelleme_kapat() {
  if grep -q 'Daha sonra' "$1"; then
    xy=$($UI tap-text "$1" "Daha sonra") && adb shell input tap $xy && echo "NOT: guncelleme penceresi kapatildi (Daha sonra)"
    sleep 2; return 0
  fi
  return 1
}
bekle_format() {
  local lim=$1 ad=$2 t=0
  while [ "$t" -lt "$lim" ]; do
    dump "$ad"
    guncelleme_kapat "$OUT/$ad.xml" && continue
    cokme_var && return 2
    $UI tap-text "$OUT/$ad.xml" "Format Seç" >/dev/null && return 0
    sleep 3; t=$((t+3))
  done
  return 1
}

adb shell svc wifi enable; adb shell svc data enable; sleep 8
adb logcat -c
dump baslangic
cokme_var && { echo "HATA: paylasim testi basinda uygulama kapali/coktu"; bitir baslangic; exit 1; }
tap tap-text "$OUT/baslangic.xml" "İndirmeler" || { echo "HATA: İndirmeler sekmesi yok"; bitir indirmeler-yok; exit 1; }
sleep 2; dump indirmeler
cokme_var && { echo "HATA: İndirmeler sekmesine geciste uygulama coktu"; bitir indirmeler-cokme; exit 1; }
adb shell "am start -n $PKG/.MainActivity -a android.intent.action.SEND -t text/plain --es android.intent.extra.TEXT 'Bak bu videoya $URL'" >/dev/null
bekle_format 120 format; r=$?
[ "$r" = 0 ] || { echo "HATA: paylasim Indirmeler sekmesinden 120 sn icinde format ekranina goturmedi (kod $r)"; bitir format; exit 1; }
echo "BASARILI: paylasim Indirmeler sekmesinden format ekranina goturdu"
cokme_var && { echo "HATA: format ekraninda uygulama coktu"; bitir format-cokme; exit 1; }

adb shell input keyevent KEYCODE_BACK; sleep 2
dump geri
cokme_var && { echo "HATA: geri tusundan sonra uygulama coktu"; bitir geri-cokme; exit 1; }
$UI tap-text "$OUT/geri.xml" "Ana Ekran" >/dev/null || { echo "HATA: geri tusu Home ekraninda kalmadi"; bitir geri-home; exit 1; }
t=0
while [ "$t" -lt 5 ]; do
  sleep 1; dump geri-bekle
  guncelleme_kapat "$OUT/geri-bekle.xml" && continue
  cokme_var && { echo "HATA: geri donus kontrolunde uygulama coktu"; bitir geri-bekle-cokme; exit 1; }
  if $UI tap-text "$OUT/geri-bekle.xml" "Format Seç" >/dev/null; then echo "HATA: geri donunce Format Seç tekrar acildi"; bitir tekrar-format; exit 1; fi
  t=$((t+1))
done
echo "BASARILI: geri donunce tekrar analiz yok"

adb shell am force-stop "$PKG"; sleep 2
# force-stop leaves the prior task record behind; clear that task as the new
# share is launched so the cold-start intent is delivered to the visible task.
adb shell "am start -f 0x10008000 -n $PKG/.MainActivity -a android.intent.action.SEND -t text/plain --es android.intent.extra.TEXT 'Bak bu videoya $URL'" >/dev/null
bekle_format 120 soguk-format; r=$?
[ "$r" = 0 ] || { echo "HATA: soguk acilista 120 sn icinde format ekrani gelmedi (kod $r)"; bitir soguk-format; exit 1; }
cokme_var && { echo "HATA: soguk acilis analizinden sonra uygulama coktu"; bitir soguk-cokme; exit 1; }
echo "BASARILI: soguk acilista paylasim analiz edildi"
bitir tamam
