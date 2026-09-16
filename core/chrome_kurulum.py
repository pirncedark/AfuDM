"""Chrome'a uzantiyi ekleme — otomatik (UI Automation) ya da adim adim elle.

Neden bu kadar dolambacli: Chrome, Web Magazasi disindaki bir uzantinin
KENDILIGINDEN kurulmasina izin vermez (kayit defteri / ilke yolu Windows'ta
yalniz kurumsal makinede calisir) ve 137'den beri `--load-extension` bayragini
da kapatti. Geriye kalan tek yol, kullanicinin yapacagi tiklamalari yapmak:
  chrome://extensions -> Gelistirici modu -> Paketlenmemis oge yukle -> klasor.

Otomasyon Windows'un kendi PowerShell + .NET UI Automation'i ile yapilir:
exe'ye ek kutuphane girmez. Fare/klavye KULLANILMAZ (Invoke/Toggle/Value
kaliplari); kullanici o sirada baska isle ugrasabilir.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import winreg
from pathlib import Path

from core import paths

CREATE_NO_WINDOW = 0x08000000

# Chrome'un arayuz dili Windows dilinden farkli olabilir: iki dil de aranir.
ADLAR = {
    "sayfa": ["Uzantılar", "Extensions"],
    "gelistirici": ["Geliştirici modu", "Developer mode"],
    "yukle": ["Paketlenmemiş öğe yükle", "Load unpacked"],
    "adres": ["Adres ve arama çubuğu", "Address and search bar"],
}

BETIK = r'''
param([string]$Klasor, [int]$HedefPid = 0, [int]$Sure = 60)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$AE = [System.Windows.Automation.AutomationElement]
$TS = [System.Windows.Automation.TreeScope]
$PC = [System.Windows.Automation.PropertyCondition]

function Yaz($adim, $durum, $mesaj = "") {
  [Console]::Out.WriteLine((@{ adim = $adim; durum = $durum; mesaj = $mesaj } | ConvertTo-Json -Compress))
  [Console]::Out.Flush()
}
function Bekle([scriptblock]$is, [double]$saniye) {
  $son = (Get-Date).AddSeconds($saniye)
  do {
    try { $v = & $is; if ($v) { return $v } } catch { }
    Start-Sleep -Milliseconds 400
  } while ((Get-Date) -lt $son)
  return $null
}
$SAYFA = @(__SAYFA__)
$GELISTIRICI = @(__GELISTIRICI__)
$YUKLE = @(__YUKLE__)
$ADRES = @(__ADRES__)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -Namespace AfuDM -Name Yerel -MemberDefinition '[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();'

function ChromePenceresi($onekler = $SAYFA) {
  $kok = $AE::RootElement
  $kosul = New-Object $PC($AE::ClassNameProperty, "Chrome_WidgetWin_1")
  foreach ($p in $kok.FindAll($TS::Children, $kosul)) {
    if ($HedefPid -and $p.Current.ProcessId -ne $HedefPid) { continue }
    foreach ($ad in $onekler) { if ($p.Current.Name.StartsWith($ad + " - ")) { return $p } }
  }
}
function DugmeBul($pencere, $adlar) {
  foreach ($ad in $adlar) {
    $kosul = New-Object $PC($AE::NameProperty, $ad)
    foreach ($o in $pencere.FindAll($TS::Descendants, $kosul)) {
      if ($o.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button) { return $o }
    }
  }
}

# 1) Uzantilar sayfasi. Chrome komut satirindan gelen chrome:// adreslerini
#    HIC acmaz (olculdu: yeni sekme acar). Python about:blank ile YENI bir sekme
#    acti; o sekmenin adres cubuguna yazilir ve tek tus (Enter) gonderilir.
#    Kullanicinin acik sekmelerine dokunulmaz.
$pencere = ChromePenceresi
if (-not $pencere) {
  $bos = Bekle { ChromePenceresi @("about:blank") } 20
  if (-not $bos) { Yaz "sayfa" "hata" "Chrome penceresi acilmadi"; exit 2 }
  $adres = Bekle {
    foreach ($ad in $ADRES) {
      $o = $bos.FindFirst($TS::Descendants, (New-Object $PC($AE::NameProperty, $ad)))
      if ($o) { return $o }
    }
  } 10
  if (-not $adres) { Yaz "sayfa" "hata" "Adres cubugu bulunamadi"; exit 2 }
  $adres.SetFocus()
  $adres.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue("chrome://extensions/")
  Start-Sleep -Milliseconds 300
  # Tus YALNIZ Chrome ondeyse gonderilir; degilse baska bir pencereye Enter gitmesin.
  if ([AfuDM.Yerel]::GetForegroundWindow() -ne [System.IntPtr]$bos.Current.NativeWindowHandle) {
    Yaz "sayfa" "hata" "Chrome one getirilemedi"; exit 2
  }
  [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
  $pencere = Bekle { ChromePenceresi } 15
}
if (-not $pencere) { Yaz "sayfa" "hata" "Chrome'da uzantilar sayfasi bulunamadi"; exit 2 }
$chromePid = $pencere.Current.ProcessId
Yaz "sayfa" "tamam"

# Zaten kurulu mu? (kart adinda AfuDM)
function KartVar {
  $kosul = New-Object $PC($AE::ControlTypeProperty, [System.Windows.Automation.ControlType]::Text)
  foreach ($o in $pencere.FindAll($TS::Descendants, $kosul)) {
    if ($o.Current.Name -like "AfuDM*") { return $true }
  }
  return $false
}

# 2) Gelistirici modu (sayfa erisilebilirlik agaci gec olusur: bekle)
$gelistirici = Bekle { DugmeBul $pencere $GELISTIRICI } 20
if (-not $gelistirici) { Yaz "gelistirici" "hata" "Gelistirici modu dugmesi bulunamadi"; exit 3 }
if (KartVar) { Yaz "gelistirici" "tamam"; Yaz "yukle" "tamam"; Yaz "klasor" "tamam"; Yaz "dogrula" "tamam" "zaten kurulu"; exit 0 }
$toggle = $gelistirici.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
if ($toggle.Current.ToggleState -ne [System.Windows.Automation.ToggleState]::On) { $toggle.Toggle() }
Yaz "gelistirici" "tamam"

# 3) Paketlenmemis oge yukle (gelistirici modu acilinca belirir)
$yukle = Bekle { DugmeBul $pencere $YUKLE } 15
if (-not $yukle) { Yaz "yukle" "hata" "Paketlenmemis oge yukle dugmesi bulunamadi"; exit 4 }
$yukle.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
Yaz "yukle" "tamam"

# 4) Klasor secme penceresi. OLCULDU: Chrome onu AYRI bir chrome.exe (utility)
#    surecinde acar ve UI Automation kok listesinde "Klasor:" kutusu / "Klasor Sec"
#    dugmesi GORUNMEZ. Win32'de ise standart kimliklerle durur (dilden bagimsiz):
#    1152 = Edit (Klasor:), 1 = Button (Klasor Sec). Yazi WM_SETTEXT, tik BM_CLICK.
Add-Type -Namespace AfuDM -Name Diyalog -MemberDefinition @"
[DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, System.IntPtr l);
delegate bool EnumProc(System.IntPtr h, System.IntPtr l);
[DllImport("user32.dll")] static extern int GetWindowThreadProcessId(System.IntPtr h, out int pid);
[DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(System.IntPtr h, System.Text.StringBuilder s, int n);
[DllImport("user32.dll")] static extern bool IsWindowVisible(System.IntPtr h);
[DllImport("user32.dll")] public static extern System.IntPtr GetDlgItem(System.IntPtr h, int id);
[DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern System.IntPtr SendMessage(System.IntPtr h, int m, System.IntPtr w, string l);
[DllImport("user32.dll")] public static extern bool PostMessage(System.IntPtr h, int m, System.IntPtr w, System.IntPtr l);
[DllImport("user32.dll")] public static extern bool IsWindow(System.IntPtr h);
public static System.IntPtr Bul(int[] pids) {
  System.IntPtr sonuc = System.IntPtr.Zero;
  EnumWindows((h, l) => {
    int pid; GetWindowThreadProcessId(h, out pid);
    var sinif = new System.Text.StringBuilder(64); GetClassName(h, sinif, 64);
    if (System.Array.IndexOf(pids, pid) >= 0 && sinif.ToString() == "#32770" && IsWindowVisible(h)
        && GetDlgItem(h, 1152) != System.IntPtr.Zero && GetDlgItem(h, 1) != System.IntPtr.Zero) {
      sonuc = h; return false;
    }
    return true;
  }, System.IntPtr.Zero);
  return sonuc;
}
"@
function Diyalog {
  $pids = [int[]]@(Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
  $h = [AfuDM.Diyalog]::Bul($pids)
  if ($h -ne [System.IntPtr]::Zero) { return $h }
}
$diyalog = Bekle { Diyalog } 15
if (-not $diyalog) { Yaz "klasor" "hata" "Klasor secme penceresi acilmadi"; exit 5 }
$WM_SETTEXT = 0x000C; $BM_CLICK = 0x00F5
for ($deneme = 0; $deneme -lt 3 -and [AfuDM.Diyalog]::IsWindow($diyalog); $deneme++) {
  # Ilk denemede tam yol; pencere klasorun ICINE girdiyse bos birakip "Klasor Sec".
  $deger = if ($deneme -eq 0) { $Klasor } else { "" }
  [void][AfuDM.Diyalog]::SendMessage([AfuDM.Diyalog]::GetDlgItem($diyalog, 1152), $WM_SETTEXT, [System.IntPtr]::Zero, $deger)
  # PostMessage: tik diyalogu kapatirken bu betik beklemede kalmasin
  [void][AfuDM.Diyalog]::PostMessage([AfuDM.Diyalog]::GetDlgItem($diyalog, 1), $BM_CLICK, [System.IntPtr]::Zero, [System.IntPtr]::Zero)
  Start-Sleep -Milliseconds 1500
}
if ([AfuDM.Diyalog]::IsWindow($diyalog)) { Yaz "klasor" "hata" "Klasor secilemedi"; exit 6 }
Yaz "klasor" "tamam"

# 5) Dogrula: AfuDM karti listede mi?
if (Bekle { KartVar } $Sure) { Yaz "dogrula" "tamam"; exit 0 }
Yaz "dogrula" "hata" "Uzanti listede gorunmedi (Chrome hata gosterdiyse sayfada yazar)"
exit 7
'''

ADIMLAR = ("sayfa", "gelistirici", "yukle", "klasor", "dogrula")


def uzanti_klasoru() -> Path:
    return paths.BASE / "extension"


def chrome_yolu() -> str:
    """Kurulu chrome.exe: once App Paths kaydi, sonra bilinen klasorler."""
    anahtar = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
    for kok in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(kok, anahtar) as k:
                yol = winreg.QueryValue(k, None)
                if yol and Path(yol).exists():
                    return yol
        except OSError:
            pass
    for taban in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"),
                  os.environ.get("LOCALAPPDATA")):
        if taban:
            aday = Path(taban) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if aday.exists():
                return str(aday)
    return ""


def sayfayi_ac(ek_argumanlar: list[str] | None = None) -> subprocess.Popen | None:
    chrome = chrome_yolu()
    if not chrome:
        return None
    # chrome:// adresi komut satirindan ACILMAZ; bos sekme acilir, adresi betik yazar.
    # Chrome aciksa istek mevcut pencereye yeni sekme olarak gider.
    return subprocess.Popen([chrome, *(ek_argumanlar or []), "about:blank"])


def panoya_kopyala(metin: str) -> bool:
    try:
        islem = subprocess.run(["clip"], input=metin.encode("utf-16-le"),
                               creationflags=CREATE_NO_WINDOW, timeout=5)
        return islem.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _betik_dosyasi() -> Path:
    def liste(anahtar: str) -> str:
        return ", ".join("'" + ad.replace("'", "''") + "'" for ad in ADLAR[anahtar])

    metin = (BETIK.replace("__SAYFA__", liste("sayfa"))
             .replace("__GELISTIRICI__", liste("gelistirici"))
             .replace("__YUKLE__", liste("yukle"))
             .replace("__ADRES__", liste("adres")))
    hedef = paths.DATA / "chrome_ekle.ps1"
    paths.DATA.mkdir(parents=True, exist_ok=True)
    # BOM'lu UTF-8: Windows PowerShell 5.1 aksi halde Turkce adlari bozar.
    hedef.write_text(metin, encoding="utf-8-sig")
    return hedef


class OtomatikEkleme:
    """Arka planda calisan tek bir ekleme denemesi; arayuz `durum()` ile izler."""

    def __init__(self) -> None:
        self._kilit = threading.Lock()
        self._durum: dict = {"calisiyor": False, "adimlar": {}, "sonuc": "", "mesaj": ""}

    def durum(self) -> dict:
        with self._kilit:
            return json.loads(json.dumps(self._durum))

    def baslat(self, ek_argumanlar: list[str] | None = None, hedef_pid: int = 0,
               once=None) -> bool:
        with self._kilit:
            if self._durum["calisiyor"]:
                return False
            self._durum = {"calisiyor": True, "adimlar": {a: "bekliyor" for a in ADIMLAR},
                           "sonuc": "", "mesaj": ""}
        threading.Thread(target=self._calis, args=(ek_argumanlar, hedef_pid, once), daemon=True).start()
        return True

    def _guncelle(self, **alanlar) -> None:
        with self._kilit:
            for anahtar, deger in alanlar.items():
                if anahtar == "adim":
                    self._durum["adimlar"][deger[0]] = deger[1]
                else:
                    self._durum[anahtar] = deger

    def _calis(self, ek_argumanlar, hedef_pid, once) -> None:
        try:
            if once:
                once()  # ornegin eslestirme penceresini ac
            if not chrome_yolu():
                self._guncelle(sonuc="hata", mesaj="chrome_yok")
                return
            islem = sayfayi_ac(ek_argumanlar)
            if hedef_pid == -1 and islem:  # test: yeni profil = yeni Chrome sureci
                hedef_pid = islem.pid
            self._guncelle(adim=("sayfa", "calisiyor"))
            komut = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                     str(_betik_dosyasi()), "-Klasor", str(uzanti_klasoru()),
                     "-HedefPid", str(max(0, hedef_pid))]
            betik = subprocess.Popen(komut, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace",
                                     creationflags=CREATE_NO_WINDOW)
            son_hata = ""
            for satir in betik.stdout:  # type: ignore[union-attr]
                satir = satir.strip()
                if not satir.startswith("{"):
                    if satir:
                        son_hata = satir[:300]
                    continue
                try:
                    olay = json.loads(satir)
                except json.JSONDecodeError:
                    continue
                self._guncelle(adim=(olay["adim"], olay["durum"]))
                if olay["durum"] == "hata":
                    son_hata = olay.get("mesaj", "")
                else:
                    sira = ADIMLAR.index(olay["adim"])
                    if sira + 1 < len(ADIMLAR):
                        self._guncelle(adim=(ADIMLAR[sira + 1], "calisiyor"))
            kod = betik.wait(timeout=180)
            self._guncelle(sonuc="kuruldu" if kod == 0 else "hata", mesaj="" if kod == 0 else son_hata)
        except Exception as exc:  # otomasyon basarisizsa elle kurulum yolu hala acik
            self._guncelle(sonuc="hata", mesaj=str(exc)[:300])
        finally:
            self._guncelle(calisiyor=False)


def bekle_bitsin(ekleme: OtomatikEkleme, zaman_asimi: float = 150) -> dict:
    son = time.time() + zaman_asimi
    while time.time() < son:
        durum = ekleme.durum()
        if not durum["calisiyor"] and durum["sonuc"]:
            return durum
        time.sleep(0.5)
    return ekleme.durum()
