# -*- coding: utf-8 -*-
param(
    [switch]$ParseOnly
)

# AfuDM offline/CI test runeri.
# - Varsayilan: tum *_test.py cevrimdisi testleri kosar (ag gerektirmez,
#   tests/smoke.py ve tests/api_smoke.py HARIC - onlar gercek indirme/ag ister).
# - -ParseOnly: hizli kontrol - tum .py dosyalari sozdizimi acisindan derlenir.
# NOT: Bu dosya BILEREK saf ASCII ile yazilmistir; PowerShell 5.1 BOM'suz
# UTF-8'i ANSI okur ve Turkce karakterler (ozellikle em-cizgi) string'leri
# bozabilir.

$ErrorActionPreference = "Stop"
$kok = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $kok
try {
    if ($ParseOnly) {
        Write-Host "[parse] tum Python dosyalari derleniyor..."
        $hatalar = 0
        Get-ChildItem -Recurse -Filter *.py -Path @("core", "api", "video", "tests") |
            Where-Object { $_.FullName -notmatch "__pycache__" } |
            ForEach-Object {
                $out = & python -m py_compile $_.FullName 2>&1
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "PARSE HATA: $($_.Name)"
                    Write-Host "$out"
                    $hatalar++
                }
            }
        if ($hatalar -gt 0) { exit 1 }
        Write-Host "[parse] OK"
        exit 0
    }

    $testler = @(
        "tests/fake_http_test.py",
        "tests/netcheck_test.py",
        "tests/manager_test.py",
        "tests/i18n_test.py",
        "tests/format_test.py",
        "tests/mux_ayristirma_test.py",
        "tests/kaydet_test.py",
        "tests/kuyruk_test.py",
        "tests/seed_test.py",
        "tests/seed_dosya_test.py",
        "tests/cerez_test.py",
        "tests/baslangic_test.py",
        "tests/iliskilendir_test.py",
        "tests/cli_test.py",
        "tests/cli_surum_test.py",
        "tests/trackerlar_test.py",
        "tests/tracker_saglik_test.py",
        "tests/db_test.py",
        "tests/network_core_test.py",
        "tests/dosya_adi_test.py",
        "tests/linkgrabber_test.py",
        "tests/engines_test.py"
    )

    $gecen = 0
    $kalan = 0
    foreach ($t in $testler) {
        if (-not (Test-Path $t)) { Write-Host "ATLANDI (yok): $t"; continue }
        $eskiEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $out = & python $t 2>&1
        $kod = $LASTEXITCODE
        $ErrorActionPreference = $eskiEAP
        if ($kod -eq 0) {
            $gecen++
            Write-Host "GECTI  $t"
        } else {
            $kalan++
            Write-Host "BASARISIZ  $t (exit $kod)"
            Write-Host ($out | Select-Object -Last 15)
        }
    }

    Write-Host ""
    Write-Host "SONUC: $gecen gecti, $kalan basarisiz"
    if ($kalan -gt 0) { exit 1 }
    exit 0
} finally {
    Pop-Location
}