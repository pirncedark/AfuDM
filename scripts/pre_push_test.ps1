# -*- coding: utf-8 -*-
# Fast, offline checks for the local pre-push hook.
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root
try {
    $tests = @(
        "tests/fake_http_test.py",
        "tests/netcheck_test.py",
        "tests/manager_test.py",
        "tests/db_test.py",
        "tests/network_core_test.py",
        "tests/cli_test.py",
        "tests/guncelleme_test.py",
        "tests/extension_pending_message_test.mjs"
    )
    foreach ($test in $tests) {
        if ($test.EndsWith(".mjs")) {
            & node $test
        } else {
            & python $test
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Pre-push test failed: $test"
            exit $LASTEXITCODE
        }
    }
} finally {
    Pop-Location
}
