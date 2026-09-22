@echo off
setlocal EnableExtensions
set PYTHONUTF8=1
chcp 65001 >nul
cd /d "%~dp0"

call START_HINT_ALPHA.bat --check
set "RC=%errorlevel%"
echo.
if "%RC%"=="0" (
  echo Hint Alpha core environment check completed.
) else (
  echo Hint Alpha core environment check found a blocking problem.
)
pause
exit /b %RC%
