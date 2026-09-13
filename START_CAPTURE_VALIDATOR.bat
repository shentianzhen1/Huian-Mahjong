@echo off
setlocal
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist ".venv-capture\Scripts\python.exe" goto missing
if /i "%~1"=="--check" goto check
".venv-capture\Scripts\python.exe" -B -m workspace.vision.capture_validator.app
if errorlevel 1 goto failed
exit /b 0
:check
".venv-capture\Scripts\python.exe" -B -m workspace.vision.capture_validator.app --help
exit /b %errorlevel%
:missing
echo Python environment not found. Run INSTALL_CAPTURE_VALIDATOR.bat first.
pause
exit /b 1
:failed
echo Capture validator failed to start. Please share the error above.
pause
exit /b 1
