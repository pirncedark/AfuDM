@echo off
rem Ilk kurulum: sadece arayuz paketlerini kurar (motorlar zaten engine/ icinde).
cd /d "%~dp0"
echo AfuDM icin gerekli Python paketleri kuruluyor...
python -m pip install --upgrade pywebview pystray pillow
echo.
echo Bitti. AfuDM.bat ile baslatabilirsin.
pause
