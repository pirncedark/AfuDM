#!/usr/bin/env bash
set -euo pipefail
OUT=e2e-out
PKG=com.afudm.afutube
UI="python3 AfuTube/scripts/ui.py"
mkdir -p "$OUT"
adb reverse tcp:8765 tcp:8765
adb shell svc wifi enable; adb shell svc data enable
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null
sleep 3

dump() { adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; adb shell cat /sdcard/ui.xml > "$OUT/$1.xml" 2>/dev/null; }
tap() { local xy; xy=$($UI "$@") || return 1; adb shell input tap $xy; }
crash_check() { adb logcat -d | grep -q 'FATAL EXCEPTION' && return 0; ! adb shell pidof "$PKG" >/dev/null; }
run_case() {
  local page="$1" expected="$2" success="$3"
  if [[ "$page" != "index.html" ]]; then adb shell input keyevent KEYCODE_BACK >/dev/null 2>&1 || true; sleep 2; fi
  dump home
  tap tap-class "$OUT/home.xml" EditText || { echo "HATA: URL alani yok ($page)"; return 1; }
  adb shell input text "http://127.0.0.1:8765/$page"; sleep 1; dump url
  tap tap-text "$OUT/url.xml" "Tarayıcıda aç" || { echo "HATA: tarayici dugmesi yok ($page)"; return 1; }
  local play=0
  for ((s=0;s<30;s+=2)); do dump page; if grep -q 'text="Oynat"' "$OUT/page.xml"; then play=1; break; fi; sleep 2; crash_check && { echo "HATA: sayfa acilirken uygulama coktu"; return 1; }; done
  [[ $play == 1 ]] || { echo "HATA: sayfa/Oynat dugmesi acilmadi ($page)"; return 1; }
  tap tap-text "$OUT/page.xml" Oynat || { echo "HATA: Oynat dugmesi tiklanamadi ($page)"; return 1; }
  local seen=0
  for ((s=0;s<20;s+=2)); do sleep 2; dump found; if grep -q 'Yakalanan videolar' "$OUT/found.xml"; then seen=1; break; fi
    crash_check && { echo "HATA: tarayici yakalama sirasinda coktu"; return 1; }
  done
  [[ $seen == 1 ]] || { echo "HATA: yakalanan videolar gorunmedi ($page)"; return 1; }
  tap tap-desc "$OUT/found.xml" "Yakalanan videolar" || { echo "HATA: yakalama listesi acilmadi ($page)"; return 1; }
  dump sheet; adb exec-out screencap -p > "$OUT/tarayici-$expected.png"
  tap tap-text "$OUT/sheet.xml" "İndir" || tap tap-text "$OUT/sheet.xml" "Indir" || { echo "HATA: Indir dugmesi yok ($page)"; return 1; }
  crash_check && { echo "HATA: indirme baslayinca uygulama coktu"; return 1; }
  adb shell input keyevent KEYCODE_BACK; sleep 1; dump browser
  tap tap-desc "$OUT/browser.xml" "Kapat" || { echo "HATA: tarayici kapatilamadi"; return 1; }
  sleep 2; dump home-download
  tap tap-text "$OUT/home-download.xml" "İndirmeler" || tap tap-text "$OUT/home-download.xml" "Indirmeler" || { echo "HATA: Indirmeler ekrani acilamadi"; return 1; }
  local done=0
  for ((s=0;s<120;s+=3)); do sleep 3; dump downloaded; if grep -q 'Tamamlandı' "$OUT/downloaded.xml" || grep -q 'Tamamland' "$OUT/downloaded.xml"; then done=1; break; fi; crash_check && { echo "HATA: indirme sirasinda uygulama coktu"; return 1; }; done
  [[ $done == 1 ]] || { echo "HATA: $expected indirme 120 sn icinde tamamlanmadi"; return 1; }
  adb exec-out screencap -p > "$OUT/tarayici-$expected-tamamlandi.png"
  echo "$success"
}
run_case index.html mp4 'BASARILI: tarayicida yakalanan MP4 indirildi'
referer_hits=$(grep -c '/clip.mp4.*Referer: http://127.0.0.1:8765/index.html' /tmp/afutube-referer.log || true)
if [[ ${referer_hits:-0} -ge 3 ]]; then echo 'BASARILI: indirme Referer ile yapildi'; else echo "HATA: indirme Referer ile yapilmadi (Referer kayitli istek: ${referer_hits:-0})"; exit 1; fi
run_case hls.html hls 'BASARILI: HLS yakalandi ve indirildi'
echo 'BASARILI: tarayici e2e adimlarinda cokme yok'
