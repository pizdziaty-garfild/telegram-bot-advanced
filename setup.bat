@echo off
REM Advanced Telegram Bot - Windows Setup Script
REM Automatyczne tworzenie venv i instalacja dependencies

echo ===== ADVANCED TELEGRAM BOT - SETUP =====
echo.

REM Sprawdzenie czy Python jest zainstalowany
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo BLAD: Python nie jest zainstalowany lub nie jest w PATH
    echo Pobierz Python z https://python.org/downloads/
    pause
    exit /b 1
)

echo [1/5] Python znaleziony: 
python --version
echo.

REM Sprawdzenie czy jestesmy w odpowiednim katalogu
if not exist "main.py" (
    echo BLAD: Nie znaleziono pliku main.py
    echo Uruchom setup.bat w katalogu z projektem telegram-bot-advanced
    pause
    exit /b 1
)

echo [2/5] Tworzenie wirtualnego srodowiska...
if exist ".venv" (
    echo Wirtualne srodowisko juz istnieje, pomijam tworzenie
) else (
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo BLAD: Nie udalo sie utworzyc venv
        pause
        exit /b 1
    )
    echo Wirtualne srodowisko utworzone pomyslnie
)
echo.

echo [3/5] Aktywacja venv i instalacja dependencies...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo BLAD: Nie udalo sie aktywowac venv
    pause
    exit /b 1
)

REM Upgrade pip
python -m pip install --upgrade pip

REM Instalacja requirements
if exist "requirements.txt" (
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo BLAD: Instalacja requirements nie powiodla sie
        pause
        exit /b 1
    )
) else (
    echo OSTRZEZENIE: Brak pliku requirements.txt
    echo Instaluje podstawowe zaleznosci...
    pip install python-telegram-bot>=20.7 pydantic>=2.5.0 pydantic-settings>=2.1.0 sqlalchemy>=2.0.0 aiosqlite>=0.19.0 alembic>=1.13.0 apscheduler>=3.10.0 tenacity>=8.2.0 pytz>=2023.3
)
echo.

echo [4/5] Tworzenie katalogow danych...
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "certs" mkdir certs
echo Katalogi utworzone: data, logs, certs
echo.

echo [5/5] Sprawdzanie konfiguracji...
if exist "config\config.example.env" (
    if not exist ".env" (
        echo Kopiuje przykladowy plik konfiguracji...
        copy "config\config.example.env" ".env"
        echo.
        echo UWAGA: Skonfiguruj plik .env z twoimi danymi:
        echo - BOT_TOKEN=twoj_token_od_botfather
        echo - OWNER_USERS=twoj_telegram_id
        echo - ADMIN_USERS=admin_telegram_ids
        echo.
    ) else (
        echo Plik .env juz istnieje
    )
) else (
    echo OSTRZEZENIE: Brak pliku config.example.env
    echo Stworz plik .env recznie z konfiguracja bota
)

echo ===== SETUP ZAKONCZONY POMYSLNIE =====
echo.
echo Aby uruchomic bota:
echo 1. Skonfiguruj plik .env
echo 2. Aktywuj venv: .venv\Scripts\activate
echo 3. Uruchom migracje: python migrations.py upgrade
echo 4. Uruchom bota: python main.py
echo.
echo Aby uruchomic testy:
echo pytest tests/
echo.
pause
