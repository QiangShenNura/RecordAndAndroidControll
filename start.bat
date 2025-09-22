@echo off
title 240fps Recording Program
cls

echo =====================================
echo    240fps Recording Program Launcher
echo =====================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please make sure venv folder exists in project directory
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if required packages are installed
echo [INFO] Checking dependencies...
py -c "import cv2, PIL" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Missing dependencies, installing...
    py -m pip install opencv-python Pillow
    echo [INFO] Dependencies installed successfully
)

echo [INFO] Starting main program...
echo =====================================
echo.

REM Run main program
py sync_measure_and_record.py

echo.
echo =====================================
echo [INFO] Program exited
echo Press any key to close window...
pause >nul
