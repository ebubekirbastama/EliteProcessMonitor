@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
%PY% -m pip install --upgrade PySide6 psutil pywintrace==0.2.0 pyinstaller
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin --name EliteProcessMonitorPro --collect-all etw EliteProcessMonitor.pyw
if errorlevel 1 goto :err
echo EXE hazir: %CD%\dist\EliteProcessMonitorPro.exe
pause
exit /b 0
:err
echo EXE olusturma basarisiz.
pause
