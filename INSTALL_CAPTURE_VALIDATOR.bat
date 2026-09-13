@echo off
setlocal
set PYTHONUTF8=1
cd /d "%~dp0"
if /i "%~1"=="--check" goto check
if exist ".venv-capture\Scripts\python.exe" goto install
py -3.12 -m venv .venv-capture
if errorlevel 1 goto missing
:install
".venv-capture\Scripts\python.exe" -m pip install -r workspace\vision\capture_validator\requirements.txt
if errorlevel 1 goto failed
echo Installation complete. Run START_CAPTURE_VALIDATOR.bat.
pause
exit /b 0
:check
if not exist ".venv-capture\Scripts\python.exe" exit /b 1
".venv-capture\Scripts\python.exe" -m pip --version
exit /b %errorlevel%
:missing
echo Python 3.12 64-bit is required to create the local environment.
echo If the py launcher is unavailable, use your Python full path:
echo python.exe -m venv .venv-capture
pause
exit /b 1
:failed
echo Dependency installation failed. Please share the error above.
pause
exit /b 1
