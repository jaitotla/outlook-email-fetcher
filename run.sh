#!/bin/bash

# This script sets up and runs the OpenMailBot backend server.
# It handles virtual environment creation, dependency installation, and server startup.

# Wrap script in main function so that a truncated partial download doesn't end
# up executing half a script.
main() {

set -eu

red="$( (/usr/bin/tput bold || :; /usr/bin/tput setaf 1 || :) 2>&-)"
green="$( (/usr/bin/tput setaf 2 || :) 2>&-)"
yellow="$( (/usr/bin/tput setaf 3 || :) 2>&-)"
plain="$( (/usr/bin/tput sgr0 || :) 2>&-)"

status() { echo "${green}>>>${plain} $*" >&2; }
error() { echo "${red}ERROR:${plain} $*" >&2; exit 1; }
warning() { echo "${yellow}WARNING:${plain} $*" >&2; }

BACKEND_DIR="backend"
VENV_DIR="$BACKEND_DIR/venv"
PYTHON_CMD="python"
PIP_CMD="pip"
ACTIVATE_CMD=""

# Cleanup function for temporary files or processes
cleanup() {
    # Add any cleanup tasks here if needed
    :
}
trap cleanup EXIT

# Check if backend directory exists
if [ ! -d "$BACKEND_DIR" ]; then
    error "Backend directory '$BACKEND_DIR' not found. Please run this script from the project root."
fi

status "Changing to backend directory..."
cd "$BACKEND_DIR" || error "Failed to change to backend directory"

# Detect OS and set appropriate commands
OS="$(uname -s)"
case "$OS" in
    Linux*|Darwin*)
        ACTIVATE_CMD="source ./venv/bin/activate"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        ACTIVATE_CMD="source ./venv/Scripts/activate"
        ;;
    *)
        warning "Unknown OS: $OS. Attempting default activation..."
        ACTIVATE_CMD="source ./venv/Scripts/activate || source ./venv/bin/activate"
        ;;
esac

# Check for Python installation and set appropriate command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PIP_CMD="pip3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    PIP_CMD="pip"
else
    error "Python is not installed. Please install Python 3.8 or higher."
fi

status "Using Python: $($PYTHON_CMD --version 2>&1)"

# Create or use existing virtual environment
if [ -d "$VENV_DIR" ]; then
    status "Virtual environment already exists at $VENV_DIR"
else
    status "Creating virtual environment..."
    if ! $PYTHON_CMD -m venv "$VENV_DIR"; then
        error "Failed to create virtual environment"
    fi
fi

# Activate virtual environment
status "Activating virtual environment..."
if ! eval "$ACTIVATE_CMD"; then
    error "Failed to activate virtual environment"
fi

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    error "requirements.txt not found in backend directory"
fi

# Install/upgrade pip, setuptools, and wheel
status "Upgrading pip, setuptools, and wheel..."
if ! $PIP_CMD install --upgrade pip setuptools wheel; then
    error "Failed to upgrade pip and dependencies"
fi

# Install requirements
status "Installing Python requirements from requirements.txt..."
if ! $PIP_CMD install -r requirements.txt; then
    error "Failed to install requirements"
fi

# Check if main.py exists
if [ ! -f "main.py" ]; then
    error "main.py not found in backend directory"
fi

status "Starting OpenMailBot backend server..."
status "Server will be running. Press Ctrl+C to stop."

# Run main.py with error handling
if $PYTHON_CMD main.py; then
    status "${green}Backend server stopped gracefully.${plain}"
else
    EXIT_CODE=$?
    error "Backend server failed with exit code $EXIT_CODE"
fi

}

main
