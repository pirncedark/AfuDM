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

tap tap-desc "$OUT/bitti.xml" "İzle" || { echo "HATA: İzle dugmesi yok"; bitir izle-yok; exit 1; }
sleep 5; dump oynatici
cokme_var && { echo "HATA: oynatici acilinca uygulama coktu"; bitir oynatici-cokme; exit 1; }
grep -q "Dinle" "$OUT/oynatici.xml" || { echo "HATA: oynaticida Dinle modu gorunmuyor"; bitir dinle-yok; exit 1; }
echo "BASARILI: İzle ile oynatici acildi, Dinle modu gorunuyor"
tap tap-desc "$OUT/oynatici.xml" "Dinle" || { echo "HATA: Dinle modu dugmesi yok"; bitir dinle; exit 1; }
sleep 1; cokme_var && { echo "HATA: Dinle moduna geciste uygulama coktu"; bitir dinle-cokme; exit 1; }
adb shell input keyevent KEYCODE_HOME; sleep 3
cokme_var && { echo "HATA: HOME sonrasi uygulama coktu"; bitir home-cokme; exit 1; }
adb shell dumpsys media_session > "$OUT/media-session.txt"
grep -A20 "com.afudm.afutube" "$OUT/media-session.txt" | grep -Eq 'state=3|state=PLAYING\(3\)' || { echo "HATA: HOME sonrasi media session PLAYING degil"; bitir arkaplan; exit 1; }
echo "BASARILI: HOME sonrasi arka plan ses oturumu PLAYING (state=3)"
adb shell monkey -p "$PKG" 1 >/dev/null 2>&1; sleep 2; dump dinleye-don
cokme_var && { echo "HATA: uygulamaya donuste uygulama coktu"; bitir dinle-donus-cokme; exit 1; }
tap tap-desc "$OUT/dinleye-don.xml" "İzle" || { echo "HATA: İzle modu dugmesi yok"; bitir izle-modu-yok; exit 1; }
sleep 1; adb shell input keyevent KEYCODE_HOME; sleep 3
cokme_var && { echo "HATA: İzle HOME sonrasi uygulama coktu"; bitir izle-home-cokme; exit 1; }
adb shell dumpsys media_session > "$OUT/media-session-izle.txt"
grep -A20 "com.afudm.afutube" "$OUT/media-session-izle.txt" | grep -Eq 'state=2|state=PAUSED\(2\)' || { echo "HATA: İzle modunda HOME sonrasi media session PAUSED degil"; bitir izle-arkaplan; exit 1; }
echo "BASARILI: İzle modunda HOME sonrasi media session PAUSED (state=2)"
adb shell monkey -p "$PKG" 1 >/dev/null 2>&1; sleep 2; adb shell input keyevent KEYCODE_BACK; sleep 2; dump listeye-don
cokme_var && { echo "HATA: listeye donuste uygulama coktu"; bitir liste-cokme; exit 1; }
for tur in 1 2 3; do
  grep -q "Tamamland" "$OUT/listeye-don.xml" && break
  adb shell monkey -p "$PKG" 1 >/dev/null 2>&1; sleep 2; dump listeye-don
  grep -q "Tamamland" "$OUT/listeye-don.xml" && break
  adb shell input keyevent KEYCODE_BACK; sleep 2; dump listeye-don
 done
grep -q "Tamamland" "$OUT/listeye-don.xml" || { echo "HATA: indirme listesine donulemedi"; bitir liste-yok; exit 1; }

echo "BASARILI: oynaticidan indirme listesine donuldu"

dump sil-oncesi
grep -q "Tamamlandı" "$OUT/sil-oncesi.xml" || { echo "HATA: Sil oncesi indirme listesi degisti"; bitir sil-liste-yok; exit 1; }
tap tap-desc "$OUT/sil-oncesi.xml" "Sil" || { echo "HATA: Sil dugmesi yok"; bitir sil; exit 1; }
sleep 3; dump silindi
if grep -q "Tamamlandı" "$OUT/silindi.xml"; then echo "HATA: Sil sonrasi kayit hala listede"; bitir sil2; exit 1; fi
echo "BASARILI: Sil kaydi kaldirdi"
bitir tamam
