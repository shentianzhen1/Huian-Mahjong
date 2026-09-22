@echo off
setlocal EnableExtensions
set PYTHONUTF8=1
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv-hint-alpha\Scripts\python.exe" goto :missing
if /i "%~1"=="--check" goto :check

".venv-hint-alpha\Scripts\python.exe" -B -m workspace.hint_alpha.app
if errorlevel 1 goto :failed
exit /b 0

:check
".venv-hint-alpha\Scripts\python.exe" -B -m workspace.hint_alpha.doctor
exit /b %errorlevel%

:missing
echo Hint Alpha environment not found. Run INSTALL_HINT_ALPHA.bat first.
pause
exit /b 1

:failed
echo Hint Alpha failed to start.
echo Run CHECK_HINT_ALPHA.bat to see which local dependency is missing.
pause
exit /b 1
