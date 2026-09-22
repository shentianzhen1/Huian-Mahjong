@echo off
setlocal EnableExtensions
set PYTHONUTF8=1
chcp 65001 >nul
cd /d "%~dp0"

set "PY="
for %%V in (3.11 3.12 3.13 3.10 3.14) do (
  if not defined PY (
    py -%%V -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] < (3,15) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] < (3,15) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY goto :missing_python

echo Using %PY%
echo [1/4] Creating Hint Alpha virtual environment...
%PY% -m venv .venv-hint-alpha
if errorlevel 1 goto :fail

echo [2/4] Installing Hint Alpha dependencies...
".venv-hint-alpha\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
".venv-hint-alpha\Scripts\python.exe" -m pip install -e ".[hint-alpha]"
if errorlevel 1 goto :fail

echo [3/4] Running environment doctor...
".venv-hint-alpha\Scripts\python.exe" -m workspace.hint_alpha.doctor --require-live
if errorlevel 1 goto :doctor_fail

echo [4/4] Ready.
echo Run START_HINT_ALPHA.bat
echo Run CHECK_HINT_ALPHA.bat any time to diagnose the local environment.
pause
exit /b 0

:missing_python
echo No supported Python was found.
echo Install 64-bit Python 3.10, 3.11, 3.12, 3.13, or 3.14 and try again.
echo The installer checks both the py launcher and python on PATH.
pause
exit /b 1

:doctor_fail
echo Installation completed, but live-capture readiness checks failed.
echo Review the Doctor output above, fix the failed item, then run CHECK_HINT_ALPHA.bat.
pause
exit /b 1

:fail
echo Installation failed. Keep this window open and copy the error for diagnosis.
pause
exit /b 1
