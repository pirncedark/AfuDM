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
} elseif (-not $ZipPath.EndsWith(".zip")) {
    $ZipPath = (Join-Path $kok "build_out\AfuDM-$ZipPath-win64.zip")
}
# NOT: Yer tutucu ("<!-- SHA256-PLACEHOLDER -->") kontrolu BURADA YAPILMAZ.
# Tabloyu release.yml paketlemeden SONRA doldurur; bu betik paketlemeden ONCE
# kosar. Burada bakmak her yayini reddeder (v2.0.0 tam bu yuzden yayinlanamadi).
# Kontrol release.yml icinde, yayinlama adiminin HEMEN ONUNDE yapilir.

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
        $eSiz = $adlar | Where-Object { $_ -like "*$g" }
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