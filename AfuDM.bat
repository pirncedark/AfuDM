@echo off
rem AfuDM baslatici — portable. Klasoru nereye kopyalarsan oradan calisir.
setlocal
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw app.py
  exit /b 0
)
where python >nul 2>nul
if %errorlevel%==0 (
  start "" /min python app.py
  exit /b 0
)
echo Python bulunamadi. Python 3.10+ kurup tekrar dene.
echo Gerekli paketler:  python -m pip install pywebview pystray pillow
pause
