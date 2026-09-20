@echo off
setlocal
cd /d "%~dp0"

set "PY=python"
where py >nul 2>nul && set "PY=py -3.11"

echo [1/3] Creating internal-test virtual environment...
%PY% -m venv .venv-hint-alpha
if errorlevel 1 goto :fail

echo [2/3] Installing Hint Alpha dependencies...
call .venv-hint-alpha\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e ".[hint-alpha]"
if errorlevel 1 goto :fail

echo [3/3] Ready.
where tesseract >nul 2>nul
if errorlevel 1 (
  echo NOTE: Tesseract is not on PATH. Capture/evidence still work, but PublicState OCR will show unavailable.
)
echo Run START_HINT_ALPHA.bat
pause
exit /b 0

:fail
echo Installation failed. Keep this window open and copy the error for diagnosis.
pause
exit /b 1
