# -*- coding: utf-8 -*-
param(
    [string]$ZipPath = ""
)

# Release zipsinin gereken dosyalari icerdigini dogrular.
# CI (release.yml) bu genel ceki paket yayinlanmadan once kosar.
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

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
try {
    $adlar = $zip.Entries | ForEach-Object { $_.FullName }
    $gerekli = @(
        "AfuDM.exe",
        "afuadm.py",
        "README.md",
        "ui/index.html",
        "extension/manifest.json",
        "core/surum.py",
        "engine/aria2c.exe"
    )
    $eksik = @()
    foreach ($g in $gerekli) {
        $gAr = $g.Replace("/", "\")
        $eSiz = $adlar | Where-Object { $_ -like "*$gAr" }
        if (-not $eSiz) { $eksik += $g }
    }
    if ($eksik.Count -gt 0) {
        Write-Host "GATE HATA - eksik dosyalar:"
        $eksik | ForEach-Object { Write-Host "  - $_" }
        Write-Host "zip icindekiler:"
        $adlar | ForEach-Object { Write-Host "  $_" }
        exit 1
    }
    $boyut = (Get-Item $ZipPath).Length / 1MB
    $boyutMetin = "{0:N1} MB" -f $boyut
    Write-Host "verify OK: $ZipPath ($boyutMetin), gerekli dosyalar mevcut"
    Write-Host "dosya sayisi: $($adlar.Count)"
    exit 0
} finally {
    $zip.Dispose()
}