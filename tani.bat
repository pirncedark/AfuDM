@echo off
setlocal EnableExtensions
chcp 65001 >nul
title AfuDM Support Diagnostics

rem This tool writes a single redacted support report and its zip beside the app.
set "ROOT=%~dp0"
pushd "%ROOT%"
set "OUTDIR=%ROOT%tanilar"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%I"
set "RAW=%OUTDIR%\support-report-%STAMP%.raw.txt"
set "REPORT=%OUTDIR%\support-report-%STAMP%.txt"
set "ZIP=%OUTDIR%\support-report-%STAMP%.zip"

echo AfuDM support diagnostics are being collected...
(
  echo AfuDM support report
  echo Generated: %DATE% %TIME%
  echo.
  echo [version]
  if exist "AfuDM.exe" (echo AfuDM.exe present) else (echo AfuDM.exe MISSING)
  if exist "AfuDM.spec" findstr /i /c:"version" "AfuDM.spec"
  echo.
  echo [system information]
  systeminfo 2>&1
  echo.
  echo [engine status]
  if exist "engine\aria2c.exe" (
    echo aria2c.exe present
    "engine\aria2c.exe" -v 2>&1
  ) else (
    echo aria2c.exe MISSING
  )
  echo.
  echo [webview2]
  reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-2347-4E85-B6E5-210F6363992E}" 2>&1
  reg query "HKCU\Software\Microsoft\EdgeUpdate\Clients\{F3017226-2347-4E85-B6E5-210F6363992E}" 2>&1
  echo.
  echo [error summary]
  powershell -NoProfile -Command "Get-ChildItem -Path '.\data' -Recurse -File -Include *.log,*.txt -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 8 | ForEach-Object { Select-String -Path $_.FullName -Pattern 'error|exception|traceback|fatal|failed|crash|hata' -CaseSensitive:$false -ErrorAction SilentlyContinue | Select-Object -Last 25 | ForEach-Object { ('{0}:{1}: {2}' -f $_.Path,$_.LineNumber,$_.Line.Trim()) } }" 2>&1
  echo.
  echo [last error]
  powershell -NoProfile -Command "Get-ChildItem -Path '.\data' -Recurse -File -Include *.log,*.txt -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 3 | ForEach-Object { '--- ' + $_.FullName + ' ---'; Get-Content $_.FullName -Tail 80 -ErrorAction SilentlyContinue }" 2>&1
) > "%RAW%"

set "AFUDM_RAW=%RAW%"
set "AFUDM_REPORT=%REPORT%"
set "AFUDM_ZIP=%ZIP%"
powershell -NoProfile -Command "$raw=$env:AFUDM_RAW; $report=$env:AFUDM_REPORT; $zip=$env:AFUDM_ZIP; $text=Get-Content -Raw $raw; $text=[regex]::Replace($text,'(?im)(token|api[_ -]?key|password|secret|cookie|authorization)\s*[:=]\s*\S+','$1=REDACTED'); $text=[regex]::Replace($text,'(?i)([?&](?:token|key|password|secret)=)[^&\s]+','$1REDACTED'); $text=[regex]::Replace($text,'(?i)[A-Z]:\\Users\\[^\\\s]+','C:\Users\REDACTED'); foreach($name in 'api_token.txt','rpc_secret.txt'){ $path=Join-Path (Get-Location) ('data\' + $name); if(Test-Path $path){ $secret=(Get-Content -Raw $path).Trim(); if($secret){ $text=$text.Replace($secret,'REDACTED') } } }; Set-Content -Path $report -Value $text -Encoding UTF8; Compress-Archive -Path $report -DestinationPath $zip -Force"
if errorlevel 1 (
  echo Diagnostics failed. The raw file has been retained: %RAW%
  popd
  exit /b 1
)
del "%RAW%"
echo.
echo Redacted report: %REPORT%
echo Zip package:     %ZIP%
echo Share only the zip package with support.
popd
endlocal
