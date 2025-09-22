@echo off
echo checking settings...

REM checking Python
py --version >nul 2>&1
if errorlevel 1 (
    echo error: cannot find Python
    pause
    exit /b 1
)

REM Create virtual environment
echo Creating virtual environment...
py -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
py -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies...
py -m pip install opencv-python Pillow

echo Setup complete!
echo Run run.bat to start the program
pause