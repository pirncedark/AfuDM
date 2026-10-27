#!/usr/bin/env bash
# AfuTube Edit sekmesi duman testi: alt çubukta Edit → "Video seç" görünür → WizardCut yeni proje ekranı açılır.
set -u
PKG=com.afudm.afutube
OUT=e2e-out
UI="python3 AfuTube/scripts/ui.py"
mkdir -p "$OUT"
dump() { adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; adb shell cat /sdcard/ui.xml > "$OUT/$1.xml" 2>/dev/null; }
tap() { local xy; xy=$($UI "$@") || return 1; adb shell input tap $xy; }
bitir() { adb exec-out screencap -p > "$OUT/edit-$1.png"; adb logcat -d > "$OUT/logcat-edit.txt"; grep -A25 "FATAL EXCEPTION" "$OUT/logcat-edit.txt" | head -60; }
cokme_var() { adb logcat -d | grep -q "FATAL EXCEPTION" || ! adb shell pidof "$PKG" >/dev/null; }

adb logcat -c
adb shell monkey -p "$PKG" 1 >/dev/null 2>&1; sleep 3
dump edit-baslangic
if grep -q 'Daha sonra' "$OUT/edit-baslangic.xml"; then tap tap-text "$OUT/edit-baslangic.xml" "Daha sonra"; sleep 2; dump edit-baslangic; fi
tap tap-text "$OUT/edit-baslangic.xml" "Edit" || { echo "HATA: Edit sekmesi yok"; bitir sekme-yok; exit 1; }
sleep 2; dump edit-sekme
grep -q 'text="Video seç"' "$OUT/edit-sekme.xml" || { echo "HATA: Edit sekmesinde Video seç yok"; bitir videosec-yok; exit 1; }
adb exec-out screencap -p > "$OUT/edit-sekme.png"
tap tap-text "$OUT/edit-sekme.xml" "Video seç" || { echo "HATA: Video seç dokunulamadı"; bitir videosec-dokun; exit 1; }
sleep 5
cokme_var && { echo "HATA: WizardCut açılırken uygulama çöktü"; bitir wizardcut-cokme; exit 1; }
adb shell dumpsys activity activities | grep -q "info.bigwizardmedia.wizardcut.MainActivity" || { echo "HATA: WizardCut ekranı açılmadı"; bitir wizardcut-yok; exit 1; }
adb exec-out screencap -p > "$OUT/edit-wizardcut.png"
adb shell input keyevent KEYCODE_BACK; sleep 1; adb shell input keyevent KEYCODE_BACK; sleep 1
echo "BASARILI: Edit sekmesi ve WizardCut açıldı"
