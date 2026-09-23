#!/usr/bin/env bash
# AfuTube indirme duman testi (e2e-acilis.sh'tan SONRA, ayni emulatorde):
# URL -> Analiz Et -> format sec -> Indir. Uygulama COKMEMELI, indirme "Tamamlandi" olmali,
# karttaki Sil dugmesi kaydi kaldirmali.
set -u
PKG=com.afudm.afutube
OUT=e2e-out
URL="${1:-https://www.w3schools.com/html/mov_bbb.mp4}"
UI="python3 AfuTube/scripts/ui.py"
mkdir -p "$OUT"

dump() { adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; adb shell cat /sdcard/ui.xml > "$OUT/$1.xml" 2>/dev/null; }
bitir() { adb exec-out screencap -p > "$OUT/indirme-$1.png"; adb logcat -d > "$OUT/logcat-indirme.txt";
          grep -A25 "FATAL EXCEPTION" "$OUT/logcat-indirme.txt" | head -60; }
cokme_var() { adb logcat -d | grep -q "FATAL EXCEPTION" || ! adb shell pidof "$PKG" >/dev/null; }
tap() { local xy; xy=$($UI "$@") || return 1; adb shell input tap $xy; }
bekle() { # bekle <sn> <dosya-adi> <ui.py argumanlari...>
  local lim=$1 ad=$2; shift 2; local t=0
  while [ $t -lt $lim ]; do dump "$ad"; $UI "$1" "$OUT/$ad.xml" "${@:2}" >/dev/null && return 0
    cokme_var && return 2; sleep 3; t=$((t+3)); done; return 1; }

adb shell svc wifi enable; adb shell svc data enable; sleep 8
adb logcat -c

dump ana
tap tap-class "$OUT/ana.xml" EditText || { echo "HATA: URL alani yok"; bitir alan; exit 1; }
sleep 1; adb shell input text "'$URL'"; sleep 1
dump url; tap tap-text "$OUT/url.xml" "Analiz Et" || { echo "HATA: Analiz Et yok"; bitir analiz; exit 1; }

bekle 120 format tap-text "Format Seç"; r=$?
[ $r = 0 ] || { echo "HATA: format ekrani gelmedi (kod $r)"; bitir format; exit 1; }
tap tap-after "$OUT/format.xml" "Video" "Ses" || { echo "HATA: secilecek format yok"; bitir format; exit 1; }
sleep 1; dump secili
tap tap-text "$OUT/secili.xml" "İndir —" || { echo "HATA: Indir dugmesi yok"; bitir indir; exit 1; }

bekle 180 bitti tap-text "Tamamlandı"; r=$?
if [ $r = 2 ]; then echo "HATA: indirme baslayinca UYGULAMA COKTU"; bitir cokme; exit 1; fi
if [ $r != 0 ]; then echo "HATA: indirme 180 sn icinde tamamlanmadi"; grep -oE 'text="[^"]+"' "$OUT/bitti.xml" | tail -8; bitir zaman; exit 1; fi
cokme_var && { echo "HATA: tamamlandi ama uygulama coktu"; bitir cokme2; exit 1; }
echo "BASARILI: indirme tamamlandi, cokme yok"

tap tap-desc "$OUT/bitti.xml" "Sil" || { echo "HATA: Sil dugmesi yok"; bitir sil; exit 1; }
sleep 3; dump silindi
if grep -q "Tamamlandı" "$OUT/silindi.xml"; then echo "HATA: Sil sonrasi kayit hala listede"; bitir sil2; exit 1; fi
echo "BASARILI: Sil kaydi kaldirdi"
bitir tamam
