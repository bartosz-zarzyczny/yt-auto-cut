@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo [1/4] Sprawdzanie systemu (wymagany winget)...
where winget >nul 2>nul
if %errorlevel% neq 0 (
    echo [BŁĄD] Brakuje narzędzia 'winget'. Upewnij sie, ze używasz zaktualizowanego Windows 10 lub 11.
    pause
    exit /b 1
)
echo System OK.

echo [2/4] Sprawdzanie środowiska Python...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Brak Pythona. Rozpoczynam cichą instalację...
    winget install --id Python.Python.3.11 -e --accept-package-agreements --accept-source-agreements
    call :UpdatePath
) else (
    echo Python jest zainstalowany.
)

echo [3/4] Instalacja pakietów z requirements.txt...
if exist "requirements.txt" (
    echo Trwa weryfikacja i instalacja bibliotek...
    python -m pip install --upgrade pip >nul 2>nul
    python -m pip install -r requirements.txt
) else (
    echo [OSTRZEŻENIE] Nie znaleziono pliku requirements.txt.
)

echo [4/4] Uruchamianie aplikacji...

python desktop_app.py

pause
exit /b 0

:UpdatePath
:: Funkcja odświeżająca zmienne środowiskowe z rejestru bez konieczności restartowania konsoli.
:: Jest to niezbędne, aby CMD "zobaczyło" polecenie python od razu po instalacji.
for /f "tokens=* usebackq" %%a in (`powershell -NoProfile -Command "$env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User'); Write-Output $env:Path"`) do (
    set "PATH=%%a"
)
goto :eof