@echo off
chcp 65001 >nul
title AfuDM Web Paneli Baslatici
echo AfuDM Web Paneli Kipinde Baslatiliyor...
echo Bu yontem Windows masaustu koprusune ihtiyac duymaz,
echo dogrudan tarayiciniz (Chrome/Edge/Brave vb.) uzerinden acar.
echo.

start "" AfuDM.exe --headless
timeout /t 2 /nobreak >nul
start http://127.0.0.1:6811/web/

echo.
echo Tarayicinizda AfuDM acildi! Bu pencereyi kapatabilirsiniz.
timeout /t 5
