@echo off
title Build AFX PC Optimizer
cd /d "%~dp0"

python -m pip install --upgrade pyinstaller psutil
if errorlevel 1 goto :error

python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "AFX-PC-Optimizer" ^
  optimizer.py
if errorlevel 1 goto :error

echo.
echo Build complete: dist\AFX-PC-Optimizer.exe
pause
exit /b 0

:error
echo.
echo Build failed. Check the error messages above.
pause
exit /b 1
