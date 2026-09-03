@echo off
setlocal

set "ROOT=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%start-networkis.ps1"
exit /b %ERRORLEVEL%
