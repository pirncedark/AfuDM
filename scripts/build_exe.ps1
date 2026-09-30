# -*- coding: utf-8 -*-
param(
    [switch]$Temiz,
    [string]$DistPath = "dist",
    [switch]$Test
)

# AfuDM.exe uretir: PyInstaller, kokteki AfuDM.spec ile. Sonuc kok klasore
# AfuDM.exe olarak yazilir (paketle.py onu pakete kopyalar).
# CI (ci.yml/release.yml) build adimlari bunu once calistirir.
# NOT: Bilerek saf ASCII - PowerShell 5.1 BOM'suz UTF-8'i ANSI okur.

$ErrorActionPreference = "Stop"
$kok = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $kok
try {
    if (-not (Test-Path "AfuDM.spec")) { Write-Host "GATE HATA: AfuDM.spec yok"; exit 1 }
    foreach ($asset in @("ui/download.html", "ui/download.js", "extension/download-handoff.js")) {
        if (-not (Test-Path $asset -PathType Leaf)) {
            Write-Host "GATE HATA: $asset yok"
            exit 1
        }
    }

    if ($Test) { $DistPath = "dist_test" }
    $distHedef = [System.IO.Path]::GetFullPath((Join-Path $kok $DistPath))
    if (-not $distHedef.StartsWith($kok + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "DistPath must be a subdirectory of the project"
    }
    $buildArgs = @("-m", "PyInstaller", "--noconfirm", "--distpath", $distHedef)
    if ($Temiz) { $buildArgs += "--clean" }
    $buildArgs += "AfuDM.spec"
    & python @buildArgs
    if ($LASTEXITCODE -ne 0) { Write-Host "PyInstaller basarisiz"; exit 1 }

    $exeKaynak = Join-Path $distHedef "AfuDM.exe"
    if (-not (Test-Path $exeKaynak)) {
        Write-Host "GATE HATA: dist\AfuDM.exe uretilmedi"
        exit 1
    }
    $hedef = Join-Path $kok "AfuDM.exe"
    $surum = & python (Join-Path $PSScriptRoot "surum_oku.py")
    if ($LASTEXITCODE -ne 0) { Write-Host "GATE HATA: surum okunamadi"; exit 1 }
    & python (Join-Path $PSScriptRoot "verify_exe.py") --exe $exeKaynak --version $surum --headless
    if ($LASTEXITCODE -ne 0) { Write-Host "GATE HATA: embedded EXE verification failed"; exit 1 }
    if ($Test -or $DistPath -ne "dist") {
        Write-Host "Test exe hazir: $exeKaynak (root exe untouched)"
        exit 0
    }
    try {
        Copy-Item -LiteralPath $exeKaynak -Destination $hedef -Force
    } catch {
        $calisan = Get-Process | Where-Object { $_.ProcessName -eq "AfuDM" }
        if ($calisan) {
            Write-Host "GATE HATA: AfuDM su an calisiyor (PID: $($calisan.Id -join ', ')) ve AfuDM.exe dosyasini kilitliyor."
            Write-Host "Uygulamayi kapatip build'i tekrar calistir - Windows calisan exe'nin uzerine yazilmasina izin vermez."
        } else {
            Write-Host "GATE HATA: AfuDM.exe kopyalanamadi: $($_.Exception.Message)"
        }
        exit 1
    }
    $boyut = (Get-Item $hedef).Length / 1MB
    $boyutMetin = "{0:N1} MB" -f $boyut
    Write-Host "exe hazir: $hedef ($boyutMetin)"
    exit 0
} finally {
    Pop-Location
}
