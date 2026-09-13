@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Quanzhou Mahjong Env V0.1 Demo
py -3 demo_env.py
echo.
pause
