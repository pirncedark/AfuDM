# -*- coding: utf-8 -*-
param(
    [string]$ZipPath = ""
)

# Release zipleri icin SHA-256 checksum uretir, <zip>.sha256 olarak yazar.
# Cikti satiri: "<hash>  <dosya-adi>". CI release.yml bunu cagirir.
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

$kayit = Get-FileHash -Path $ZipPath -Algorithm SHA256
$ad = Split-Path $ZipPath -Leaf
$satir = "$($kayit.Hash.ToLower())  $ad"
$MapPath = $ZipPath + ".sha256"
Set-Content -LiteralPath $MapPath -Value $satir -Encoding ascii
Write-Host "checksum: $MapPath"
Write-Host $satir
exit 0