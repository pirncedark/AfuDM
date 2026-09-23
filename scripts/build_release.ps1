# -*- coding: utf-8 -*-
param(
    [string]$Tag = "",
    [switch]$Full
)

# Release paketi uretir. CI (release.yml) tarafindan cagrilir; elle de
# calisir (git tag vX.Y.Z ile).
# Gate: tag varsa core/surum.py ile eslesmeli; tag == HEAD olmak CI'nin
# isidir (bu betik yalniz surum tutarliligini dogrular).
$ErrorActionPreference = "Stop"
$kok = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $kok
try {
    $surum = & python (Join-Path $PSScriptRoot "surum_oku.py")
    if ($LASTEXITCODE -ne 0) { Write-Output "surum.py okunamadi"; exit 1 }
    Write-Output "surum.py: $surum"

    if ($Tag) {
        if ($Tag -ne "v$surum") {
            Write-Output "GATE HATA: beklenen: v$surum, gelen: $Tag"
            exit 1
        }
        Write-Output "gate: tag $Tag ile surum eslesiyor"
    } else {
        Write-Output "gate: tag verilmedi, yalniz build"
    }

    $argTum = if ($Full) { "--tam" } else { "" }
    $distExe = Join-Path $kok "dist\AfuDM.exe"
    $rootExe = Join-Path $kok "AfuDM.exe"
    $surumPy = Join-Path $kok "core\surum.py"
    $appPy = Join-Path $kok "app.py"
    if (-not (Test-Path $distExe -PathType Leaf)) {
        Write-Output "GATE HATA: dist\AfuDM.exe yok; once PyInstaller derlemesi yapilmali"
        exit 1
    }
    $distZaman = (Get-Item $distExe).LastWriteTimeUtc
    foreach ($kaynak in @($surumPy, $appPy)) {
        if ($distZaman -lt (Get-Item $kaynak).LastWriteTimeUtc) {
            Write-Output "GATE HATA: dist\AfuDM.exe eski: $kaynak"
            exit 1
        }
    }
    if (Test-Path $rootExe -PathType Leaf) {
        $rootZaman = (Get-Item $rootExe).LastWriteTimeUtc
        foreach ($kaynak in @($surumPy, $appPy)) {
            if ($rootZaman -lt (Get-Item $kaynak).LastWriteTimeUtc) {
                Write-Output "GATE HATA: AfuDM.exe eski: $kaynak"
                exit 1
            }
        }
    }
    Copy-Item -LiteralPath $distExe -Destination $rootExe -Force
    & python paketle.py $argTum
    if ($LASTEXITCODE -ne 0) { Write-Output "paketle.py basarisiz"; exit 1 }

    $cikti = Join-Path $kok "build_out\paket\AfuDM"
    if (-not (Test-Path (Join-Path $cikti "AfuDM.exe"))) {
        Write-Output "GATE HATA: paket icinde AfuDM.exe yok (kokte mi?)"
        exit 1
    }
    Write-Output "paket hazir: $cikti"
    exit 0
} finally {
    Pop-Location
}
