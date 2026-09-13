@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Quanzhou Mahjong Assistant V0.4 Installer

echo ==================================================
echo Quanzhou Mahjong Assistant V0.4
echo iPhone mirror test / Two-player first
echo ==================================================
echo.

set PYEXE=

for %%V in (3.12 3.13 3.14) do (
  py -%%V -c "import sys" >nul 2>&1
  if not errorlevel 1 (
    if not defined PYEXE set "PYEXE=py -%%V"
  )
)

if not defined PYEXE (
  py -3 -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PYEXE=py -3"
)

if not defined PYEXE (
  echo [ERROR] Python was not found.
  echo Recommended: Python 3.12 64-bit.
  echo You may keep Python 3.14 installed side-by-side.
  pause
  exit /b 1
)

echo [1/5] Python:
%PYEXE% -c "import sys; print(sys.executable); print(sys.version)"
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [2/5] Creating local virtual environment...
  %PYEXE% -m venv .venv
  if errorlevel 1 goto :fail
) else (
  echo [2/5] Local environment already exists.
)

echo [3/5] Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail

echo [4/5] Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :compat

echo [5/5] Checking modules...
".venv\Scripts\python.exe" -c "import cv2,numpy,PIL,mss,win32gui; print('All dependencies OK')"
if errorlevel 1 goto :fail

echo.
echo Installation complete. Starting program...
".venv\Scripts\python.exe" app.py
exit /b 0

:compat
echo.
echo [ERROR] Dependency installation failed.
echo If the error mentions OpenCV or NumPy compatibility,
echo install Python 3.12 64-bit and run this file again.
echo You do NOT need to uninstall Python 3.14.
pause
exit /b 1

:fail
echo.
echo [ERROR] Installation failed.
echo Please take a screenshot of this window and send it to me.
pause
exit /b 1
