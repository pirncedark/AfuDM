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
        Write-Host "[parse] tum PowerShell betikleri Windows PowerShell 5.1 ile denetleniyor..."
        Write-Host "[parse] tum Python dosyalari derleniyor..."
        $hatalar = 0
        Get-ChildItem -Filter *.ps1 -Path "scripts" | ForEach-Object {
            $goreliYol = Join-Path "scripts" $_.Name
            $baytlar = [System.IO.File]::ReadAllBytes($_.FullName)
            $baslangic = 0
            if ($baytlar.Length -ge 3 -and $baytlar[0] -eq 0xEF -and $baytlar[1] -eq 0xBB -and $baytlar[2] -eq 0xBF) {
                $baslangic = 3
            }
            $satir = 1
            $raporlananSatirlar = @{}
            for ($i = $baslangic; $i -lt $baytlar.Length; $i++) {
                if ($baytlar[$i] -eq 0x0A) {
                    $satir++
                } elseif ($baytlar[$i] -gt 0x7F -and -not $raporlananSatirlar.ContainsKey($satir)) {
                    Write-Host ("ASCII disi karakter (BOM'suz dosyada PowerShell 5.1 kirilir): {0}:{1}" -f $goreliYol, $satir)
                    $raporlananSatirlar[$satir] = $true
                    $hatalar++
                }
            }

            $guvenliYol = $_.FullName.Replace("'", "''")
            $parseKomutu = @"
`$tokenler = `$null
`$parseHatalari = `$null
[void][System.Management.Automation.Language.Parser]::ParseFile('$guvenliYol', [ref]`$tokenler, [ref]`$parseHatalari)
if (`$parseHatalari) {
    foreach (`$parseHatasi in `$parseHatalari) {
        Write-Output ('{0}:{1}: {2}' -f `$parseHatasi.Extent.File, `$parseHatasi.Extent.StartLineNumber, `$parseHatasi.Message)
    }
    exit 1
}
"@
            $out = & powershell -NoProfile -Command $parseKomutu 2>&1
            if ($LASTEXITCODE -ne 0) {
                Write-Host "PARSE HATA: $goreliYol"
                Write-Host $out
                $hatalar++
            }
        }
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
        "tests/torrent_dosya_test.py",
        "tests/torrent_secim_test.py",
        "tests/network_core_test.py",
        "tests/dosya_adi_test.py",
        "tests/linkgrabber_test.py",
        "tests/engines_test.py",
        "tests/video_pro_test.py",
        "tests/cli_yardim_test.py",
        "tests/video_cerez_test.py",
        "tests/torrent_ui_test.py",
        "tests/torrent_onekle_test.py",
        "tests/torrent_duzeltme_test.py",
        "tests/v175_ayar_test.py",
        "tests/pwa_test.py",
        "tests/torrent_yaris_test.mjs"
    )

    $gecen = 0
    $kalan = 0
    foreach ($t in $testler) {
        if (-not (Test-Path $t)) { Write-Host "ATLANDI (yok): $t"; continue }
        $eskiEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        if ($t.EndsWith(".mjs") -or $t.EndsWith(".js")) {
            $out = & node $t 2>&1
        } else {
            $out = & python $t 2>&1
        }
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
