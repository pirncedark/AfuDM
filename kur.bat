@echo off
rem Ilk kurulum: sadece arayuz paketlerini kurar (motorlar zaten engine/ icinde).
cd /d "%~dp0"
echo AfuDM icin gerekli Python paketleri kuruluyor...
rem qrcode: telefondan baglanma ekranindaki kare kod (Ayarlar > Telefondan baglan)
python -m pip install --upgrade pywebview pystray pillow qrcode
echo.
echo Bitti. AfuDM.bat ile baslatabilirsin.
pause
