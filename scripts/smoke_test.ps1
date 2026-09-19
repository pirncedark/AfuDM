# -*- coding: utf-8 -*-
param(
    [string]$ZipPath = ""
)

# Yayinlanan paketin "aci ve calis" sinayan hafif duman testi.
# Genel gezi: zip acilir, kritik dosyalar yerinde mi diye bakilir.
# Gercek UI/indirme testi CI disinda (manuel veya online smoke) yapilir.
# NOT: Bilerek saf ASCII - PowerShell 5.1 BOM'suz UTF-8'i ANSI okur.

$ErrorActionPreference = "Stop"
$kok = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $ZipPath) {
    $sira = Get-ChildItem (Join-Path $kok "build_out") -Filter "AfuDM-v*.zip" |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $sira) { Write-Host "zip bulunamadi"; exit 1 }
    $ZipPath = $sira.FullName
}
if (-not (Test-Path $ZipPath)) { Write-Host "zip yok: $ZipPath"; exit 1 }

$gecici = Join-Path $env:TEMP ("afudm_smoke_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $gecici | Out-Null
try {
    Expand-Archive -Path $ZipPath -DestinationPath $gecici -Force
    $ic = Join-Path $gecici "AfuDM"
    $exe = Join-Path $ic "AfuDM.exe"
    if (-not (Test-Path $exe)) { Write-Host "GATE HATA: AfuDM.exe yok"; exit 1 }
    $core = Join-Path $ic "core"
    if (-not (Test-Path (Join-Path $core "surum.py"))) { Write-Host "GATE HATA: core/surum.py yok"; exit 1 }
    $ui = Join-Path $ic "ui\index.html"
    if (-not (Test-Path $ui)) { Write-Host "GATE HATA: ui/index.html yok"; exit 1 }

    Write-Host "smoke OK: $ZipPath acildi, yapi yerinde ($gecici)"
    exit 0
} finally {
    Remove-Item -LiteralPath $gecici -Recurse -Force -ErrorAction SilentlyContinue
}