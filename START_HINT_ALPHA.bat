@echo off
setlocal
cd /d "%~dp0"
if exist ".venv-hint-alpha\Scripts\python.exe" (
  ".venv-hint-alpha\Scripts\python.exe" -m workspace.hint_alpha.app
) else (
  echo Hint Alpha environment not found. Run INSTALL_HINT_ALPHA.bat first.
  pause
)
