# -*- coding: utf-8 -*-
param(
    [string]$ZipPath = "",
    [ValidateSet("Rust")][string]$PackageType = "Rust"
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

if ($PackageType -eq "Rust") {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "verify_release.ps1") $ZipPath -PackageType Rust
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    # Python paketindeki gibi yalniz yapi denetimi: EXE burada baslatilmaz (uretim
    # aria2 6810..6830 araligini ve tek-ornek kilidini kullanir). Calisma zamani
    # kapsami rs/tests_hata (test-kapisi exe, izole veri/port) ile saglanir.
    Write-Host "smoke OK (yapi): $ZipPath Rust paketi dogrulandi; EXE baslatilmadi"
    exit 0
}
