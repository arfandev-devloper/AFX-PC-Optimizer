@echo off
title AFX PC Optimizer
cd /d "%~dp0"
python optimizer.py
if errorlevel 1 (
    echo.
    echo AFX PC Optimizer exited with an error.
    echo Make sure Python and requirements are installed.
    pause
)
