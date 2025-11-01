@echo off
REM ========================================
REM Advanced Telegram Bot - Development Runner
REM ========================================

echo.
echo ========================================
echo  Starting Advanced Telegram Bot
echo ========================================
echo.

REM Check if virtual environment exists
if not exist venv (
    echo ERROR: Virtual environment not found!
    echo Please run setup.bat first to install dependencies
    pause
    exit /b 1
)

REM Check if .env exists
if not exist .env (
    echo ERROR: Configuration file .env not found!
    echo Please run setup.bat first to create configuration
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Create logs directory if it doesn't exist
if not exist logs mkdir logs

REM Run the bot
echo Starting bot in polling mode...
echo Press Ctrl+C to stop the bot
echo.
python main.py

echo.
echo Bot stopped.
pause
