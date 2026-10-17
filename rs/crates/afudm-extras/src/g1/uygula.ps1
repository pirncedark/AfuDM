$ErrorActionPreference = "Stop"
$base = __BASE__
$source = __SOURCE__
$backup = __BACKUP__
$pidToWait = __PID__
while (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 400 }
$skip = @("data", "downloads", "plugins")
# Yalniz yeni paketin ust duzeyinde bulunan ogeler yedeklenir/degistirilir;
# BASE beklenmedik bir klasor olsa bile baska dosyalara dokunulmaz.
$items = @(Get-ChildItem -LiteralPath $source -Force | Where-Object { $skip -notcontains $_.Name } | ForEach-Object { $_.Name })
# engine: kullanicinin sonradan indirdigi araclar (yt-dlp, ffmpeg) silinmez, yalniz uzerine yazilir.
$merge = @("engine")
if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Recurse -Force }
New-Item -ItemType Directory -Force -Path $backup | Out-Null
try {
  foreach ($n in $items) { $p = Join-Path $base $n; if (Test-Path -LiteralPath $p) { Copy-Item -LiteralPath $p -Destination $backup -Recurse -Force } }
} catch {
  exit 1
}
try {
  foreach ($n in $items) {
    $p = Join-Path $base $n
    if (($merge -notcontains $n) -and (Test-Path -LiteralPath $p)) { Remove-Item -LiteralPath $p -Recurse -Force }
    if ($merge -contains $n) {
      New-Item -ItemType Directory -Force -Path $p | Out-Null
      Get-ChildItem -LiteralPath (Join-Path $source $n) -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $p -Recurse -Force }
    } else {
      Copy-Item -LiteralPath (Join-Path $source $n) -Destination $base -Recurse -Force
    }
  }
} catch {
  foreach ($n in $items) {
    $p = Join-Path $base $n
    $b = Join-Path $backup $n
    if (Test-Path -LiteralPath $b) {
      if ($merge -contains $n) { Get-ChildItem -LiteralPath $b -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $p -Recurse -Force } }
      else { if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force }; Copy-Item -LiteralPath $b -Destination $base -Recurse -Force }
    }
  }
  exit 1
}
Start-Process -FilePath (Join-Path $base "AfuDM.exe")
