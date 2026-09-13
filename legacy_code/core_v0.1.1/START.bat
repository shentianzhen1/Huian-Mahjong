@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Quanzhou Mahjong Core V0.1
py -3 manual_tester.py
if errorlevel 1 (
  echo.
  echo Program exited with an error.
  echo Please take a screenshot and send it to me.
  pause
)
