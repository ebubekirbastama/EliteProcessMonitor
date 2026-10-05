@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ETW Onarim
net session >nul 2>&1
if not %errorlevel%==0 (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ComSpec%' -ArgumentList '/c','""%~f0""' -WorkingDirectory '%~dp0' -Verb RunAs"
  exit /b
)
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
%PY% -m pip uninstall -y pywintrace
%PY% -m pip install --no-cache-dir pywintrace==0.2.0
%PY% -c "import etw,sys; print('ETW OK'); print(etw.__file__); print(sys.executable)"
echo.
pause
