@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Quanzhou Mahjong Core V0.1 Tests
py -3 -m unittest discover -s tests -v
echo.
pause
