@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Elite Process Monitor Pro v8 - Kurulum ve Onarim

net session >nul 2>&1
if not %errorlevel%==0 (
  echo Yonetici izni isteniyor...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%ComSpec%' -ArgumentList '/c','""%~f0""' -WorkingDirectory '%~dp0' -Verb RunAs"
  exit /b
)

where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)

echo [1/4] Python kontrol ediliyor...
%PY% -c "import sys; print(sys.version); print(sys.executable)"
if errorlevel 1 goto :err

echo [2/4] Gerekli paketler kuruluyor...
%PY% -m pip install --upgrade pip
if errorlevel 1 goto :err
%PY% -m pip install --upgrade PySide6 psutil pyinstaller pywintrace==0.2.0
if errorlevel 1 goto :err

echo [3/4] ETW modulu test ediliyor...
%PY% -c "import etw,sys; print('ETW OK:', etw.__file__); print('Python:',sys.executable)"
if errorlevel 1 (
  echo.
  echo ETW modulu yuklenemedi. Ayrintili test yapiliyor...
  %PY% -m pip show pywintrace
  %PY% -c "import traceback; import etw"
  goto :err
)

echo [4/4] Program baslatiliyor...
for /f "delims=" %%I in ('%PY% -c "import sys,pathlib; print(pathlib.Path(sys.executable).with_name('pythonw.exe'))"') do set PYW=%%I
if not exist "%PYW%" set PYW=pythonw.exe
start "" "%PYW%" "%~dp0EliteProcessMonitor.pyw"
exit /b 0

:err
echo.
echo Kurulum/onarim basarisiz. Yukaridaki hata metnini gonderebilirsiniz.
pause
exit /b 1
