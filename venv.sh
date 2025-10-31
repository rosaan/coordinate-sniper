#!/bin/bash

# Script to set up and activate Python virtual environment
# Supports Windows, Linux, and macOS

VENV_DIR="venv"

# Detect operating system
OS="$(uname -s)"
case "${OS}" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    CYGWIN*)    MACHINE=Windows;;
    MINGW*)     MACHINE=Windows;;
    MSYS*)      MACHINE=Windows;;
    *)          MACHINE="UNKNOWN:${OS}"
esac

echo "Detected OS: $MACHINE"

# Determine Python command and activation script path
if [[ "$MACHINE" == "Windows" ]]; then
    PYTHON_CMD="python"
    ACTIVATE_SCRIPT="$VENV_DIR/Scripts/activate"
    PIP_CMD="$VENV_DIR/Scripts/pip"
else
    PYTHON_CMD="python3"
    ACTIVATE_SCRIPT="$VENV_DIR/bin/activate"
    PIP_CMD="$VENV_DIR/bin/pip"
fi

# Check if virtual environment already exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment"
        exit 1
    fi
    
    echo "Virtual environment created successfully!"
else
    echo "Virtual environment already exists."
fi

# Activate the virtual environment
echo "Activating virtual environment..."
if [[ "$MACHINE" == "Windows" ]]; then
    # On Windows, use the batch file or PowerShell
    if [ -f "$VENV_DIR/Scripts/activate.bat" ]; then
        source "$VENV_DIR/Scripts/activate.bat" 2>/dev/null || . "$VENV_DIR/Scripts/activate"
    else
        source "$VENV_DIR/Scripts/activate"
    fi
else
    source "$ACTIVATE_SCRIPT"
fi

# Install/upgrade pip
echo "Upgrading pip..."
$PIP_CMD install --upgrade pip

# Install requirements if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing requirements..."
    
    # On Windows, install all packages including pywin32
    # On Linux/Mac, skip pywin32 as it's Windows-only
    if [[ "$MACHINE" == "Windows" ]]; then
        echo "Installing all packages (including Windows-specific pywin32)..."
        $PIP_CMD install -r requirements.txt
    else
        echo "Installing packages (skipping Windows-specific pywin32)..."
        # Create a temporary requirements file without pywin32
        grep -v "^pywin32" requirements.txt > requirements_temp.txt || cat requirements.txt > requirements_temp.txt
        $PIP_CMD install -r requirements_temp.txt
        rm -f requirements_temp.txt
    fi
else
    echo "Warning: requirements.txt not found. Skipping package installation."
fi

echo ""
echo "Virtual environment is ready!"
if [[ "$MACHINE" == "Windows" ]]; then
    echo "To activate it manually later, run: $VENV_DIR\\Scripts\\activate"
else
    echo "To activate it manually later, run: source $VENV_DIR/bin/activate"
fi
echo "To deactivate, run: deactivate"

