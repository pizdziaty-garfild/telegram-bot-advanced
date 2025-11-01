@echo off
REM ========================================
REM Advanced Telegram Bot - Windows Setup
REM ========================================

echo.
echo ========================================
echo  Advanced Telegram Bot - Setup Script
echo ========================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

REM Create virtual environment
echo.
echo Creating virtual environment...
if exist venv (
    echo Virtual environment already exists, removing old one...
    rmdir /s /q venv
)
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

REM Create directories
echo.
echo Creating required directories...
if not exist logs mkdir logs
if not exist data mkdir data
if not exist certs mkdir certs

REM Setup configuration
echo.
echo Setting up configuration...
if not exist .env (
    echo Copying configuration template...
    copy config\config.example.env .env
    echo.
    echo ============================================
    echo  IMPORTANT: Configure your bot settings!
    echo ============================================
    echo.
    echo Edit .env file with your settings:
    echo - BOT_TOKEN: Get from @BotFather on Telegram
    echo - ADMIN_USERS: Your Telegram user ID (get from @userinfobot)
    echo - OWNER_USERS: Your Telegram user ID
    echo.
    echo Press any key to open .env file for editing...
    pause >nul
    notepad .env
) else (
    echo Configuration file .env already exists.
)

echo.
echo ========================================
echo  Setup completed successfully!
echo ========================================
echo.
echo Next steps:
echo 1. Make sure .env file is configured with your bot token
echo 2. Run the bot using: run_dev.bat
echo.
pause
