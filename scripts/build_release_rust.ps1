# Rust portable release. No user data or Python runtime is staged.
param([string]$Tag = "", [switch]$Offline)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root
try {
    $version = & python scripts/surum_oku.py
    if ($LASTEXITCODE -ne 0) { throw "surum.py okunamadi" }
    if ($Tag -and $Tag -ne "v$version") { throw "Tag/surum.py uyusmuyor: $Tag / $version" }
    & python -c "import json,pathlib,sys,tomllib; r=pathlib.Path('.'); v=sys.argv[1]; versions=[tomllib.loads((r/'rs/Cargo.toml').read_text(encoding='utf-8'))['workspace']['package']['version'],tomllib.loads((r/'rs/app/Cargo.toml').read_text(encoding='utf-8'))['package']['version'],json.loads((r/'rs/app/tauri.conf.json').read_text(encoding='utf-8'))['version']]; print('version gate:',v,versions); sys.exit(0 if all(x==v for x in versions) else 1)" $version
    if ($LASTEXITCODE -ne 0) { throw "Rust/Tauri/surum.py uyusmuyor" }
    $engine = Join-Path $root "engine/aria2c.exe"
    if (-not (Test-Path -LiteralPath $engine -PathType Leaf)) { throw "engine/aria2c.exe eksik" }
    $cargoArgs = @("build", "--release", "--locked", "--no-default-features", "--manifest-path", "rs/app/Cargo.toml")
    if ($Offline) { $cargoArgs += "--offline" }
    & cargo @cargoArgs
    if ($LASTEXITCODE -ne 0) { throw "Rust release derlemesi basarisiz" }
    $metadataArgs = @("metadata", "--no-deps", "--format-version", "1", "--locked", "--manifest-path", "rs/app/Cargo.toml")
    if ($Offline) { $metadataArgs += "--offline" }
    $metadata = & cargo @metadataArgs
    if ($LASTEXITCODE -ne 0) { throw "Cargo hedef yolu okunamadi" }
    $target = ($metadata | ConvertFrom-Json).target_directory
    $binary = Join-Path $target "release/AfuDM.exe"
    if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) { throw "Rust AfuDM.exe bulunamadi" }
    # A unique staging directory avoids deleting or including older Python output.
    $stage = Join-Path $root ("build_out/rust-stage-" + [guid]::NewGuid().ToString("N"))
    $app = Join-Path $stage "AfuDM"
    New-Item -ItemType Directory -Path (Join-Path $app "engine") -Force | Out-Null
    Copy-Item -LiteralPath $binary -Destination (Join-Path $app "AfuDM.exe")
    Copy-Item -LiteralPath $engine -Destination (Join-Path $app "engine/aria2c.exe")
    # Tauri embeds app/ui and icons; extension is read next to the EXE.
    Copy-Item -LiteralPath (Join-Path $root "extension") -Destination $app -Recurse
    $zip = Join-Path $root "build_out/AfuDM-v$version-win64.zip"
    if (Test-Path -LiteralPath $zip) { throw "Zip zaten var; mevcut cikti korunuyor: $zip" }
    Compress-Archive -LiteralPath $app -DestinationPath $zip
    # Never mix the Rust package with stale Python staging.
    $canonical = Join-Path $root "build_out/paket/AfuDM"
    if (Test-Path -LiteralPath $canonical) { throw "Staging zaten var; mevcut cikti korunuyor: $canonical (yeni zip: $zip)" }
    New-Item -ItemType Directory -Path (Split-Path $canonical) -Force | Out-Null
    Copy-Item -LiteralPath $app -Destination $canonical -Recurse
    Write-Output "Rust paket hazir: $canonical"
    Write-Output "Rust zip hazir: $zip"
} finally {
    Pop-Location
}
