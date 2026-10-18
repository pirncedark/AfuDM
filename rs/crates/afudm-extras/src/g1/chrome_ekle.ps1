
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
[DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern System.IntPtr SendMessageTimeout(System.IntPtr h, int m, System.IntPtr w, string l, int f, int t, out System.IntPtr res);
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
  # DIKKAT: burada $HedefPid KULLANILMAZ. Chrome klasor secme penceresini AYRI bir
  # chrome.exe surecinde acar; pencere sahibi hedef PID degil. Yalnizca hedef PID'e
  # bakmak pencereyi gormeyi engeller ("Klasor secme penceresi acilmadi").
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
  $res = [System.IntPtr]::Zero
  [void][AfuDM.Diyalog]::SendMessageTimeout([AfuDM.Diyalog]::GetDlgItem($diyalog, 1152), $WM_SETTEXT, [System.IntPtr]::Zero, $deger, 2, 2000, [ref]$res)
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
