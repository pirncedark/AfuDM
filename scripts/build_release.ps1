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
    if (-not (Test-Path (Join-Path $kok "AfuDM.exe"))) {
        Write-Host "AfuDM.exe yok — build_exe.ps1 ile uretiliyor..."
        & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "build_exe.ps1")
        if ($LASTEXITCODE -ne 0) { Write-Host "exe uretilemedi"; exit 1 }
    }
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