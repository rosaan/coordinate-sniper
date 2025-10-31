@echo off
REM Script to set up and activate Python virtual environment for Windows

set VENV_DIR=venv

echo Detected OS: Windows

REM Check if virtual environment already exists
if not exist "%VENV_DIR%" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
    
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        exit /b 1
    )
    
    echo Virtual environment created successfully!
) else (
    echo Virtual environment already exists.
)

REM Activate the virtual environment
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

REM Install/upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements if requirements.txt exists
if exist "requirements.txt" (
    echo Installing all packages (including Windows-specific pywin32)...
    pip install -r requirements.txt
) else (
    echo Warning: requirements.txt not found. Skipping package installation.
)

echo.
echo Virtual environment is ready!
echo To activate it manually later, run: %VENV_DIR%\Scripts\activate.bat
echo To deactivate, run: deactivate

