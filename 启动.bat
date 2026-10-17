@echo off
setlocal
cd /d "%~dp0"

rem  All text in this file is ASCII on purpose.
rem  cmd.exe reads .bat files using the system ANSI codepage (GBK on a
rem  Chinese Windows), so a UTF-8 file with Chinese comments gets decoded
rem  into garbage and the lines break apart. Keep it ASCII here.
rem
rem  Runs the Qt app from the project-local venv, never through the exe,
rem  so SmartScreen never appears.

set "PYW=%~dp0.venv\Scripts\pythonw.exe"
set "PY=%~dp0.venv\Scripts\python.exe"
set "APP=%~dp0app_qt.py"

if not exist "%APP%" goto noapp
if not exist "%PY%" goto nodeps

if exist "%PYW%" (
    start "" "%PYW%" "%APP%"
) else (
    start "" "%PY%" "%APP%"
)
exit /b 0

:nodeps
echo.
echo   PySide6 is not installed yet.
echo.
echo   Open a terminal in this folder and run:
echo.
echo       python -m venv --without-pip --system-site-packages .venv
echo       .venv\Scripts\python.exe -m pip install PySide6_Essentials
echo.
pause
exit /b 1

:noapp
echo.
echo   app_qt.py not found next to this script.
echo.
pause
exit /b 1
