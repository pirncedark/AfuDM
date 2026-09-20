@echo off
chcp 65001 >nul
title AfuDM Hata Ayiklama (Debug) Modu
echo AfuDM Debug Modunda Baslatiliyor...
echo Ekrana dusen loglari ve hata mesajlarini buradan gorebilirsiniz.
echo Arayuz acilinca klavyeden F12 tusuna basarak DevTools konsolunu acabilirsiniz.
echo.

set AFUDM_DEBUG=1
AfuDM.exe
echo.
echo AfuDM kapandi. Hata loglarini inceleyebilirsiniz.
pause
