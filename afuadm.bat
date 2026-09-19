@echo off
rem afuadm — AfuDM komut satiri araci. Tek dosya, portable.
rem Ornek:  afuadm list   /   afuadm mode snail   /   afuadm --help
rem
rem Not: klasor yolunda BOSLUK olsa bile (%USERPROFILE%\My Tools\AfuDM gibi)
rem calisir: tum yollarda guvenli guvence saglanir (%~dp0 ile).
setlocal
set "ROOT=%~dp0"
where py >nul 2>nul && set "PY=py" || set "PY=python"
"%PY%" "%ROOT%afuadm.py" %*
set "CC=%ERRORLEVEL%"
exit /b %CC%