@echo off
rem Set encoding to UTF-8 to ensure stability
chcp 65001 >nul

rem Lock working directory to your project path
cd /d "G:\AutoAI_01"

:menu
cls
echo ========================================================
echo                 AutoAI Control Center
echo ========================================================
echo.
echo  [ CORE POWER ZONE ]
echo   1. Start All (Keep Existing Chrome + Server)
echo   2. Start Server Only (No browser launch)
echo   3. Force Reset Chrome (Clean restart for Port 9222)
echo.
echo  [ DATA AND MAINTENANCE ]
echo   4. Clean Logs (Empty logs/sys_logs.log)
echo   5. Reset Queue (Delete queue_backup.json)
echo   6. Backup DB (Create safety copy of history.db)
echo.
echo  [ QUICK NAVIGATION ]
echo   7. Open Downloads Folder
echo   8. Ghost Kill (Force terminate Python and Chrome)
echo.
echo  [ VIRTUAL ENVIRONMENT ]
echo   9. Open Venv Shell (Activate environment in new window)
echo.
echo   0. Exit Console
echo ========================================================
set "choice="
set /p choice="Enter choice and press ENTER: "

if "%choice%"=="1" goto start_all
if "%choice%"=="2" goto start_server
if "%choice%"=="3" goto reset_chrome
if "%choice%"=="4" goto clean_logs
if "%choice%"=="5" goto reset_queue
if "%choice%"=="6" goto backup_db
if "%choice%"=="7" goto open_downloads
if "%choice%"=="8" goto kill_all
if "%choice%"=="9" goto venv_shell
if "%choice%"=="0" exit
goto menu

:start_all
echo.
echo [1/3] Checking for Chrome instances...
echo [2/3] Launching or focusing Chrome on Port 9222...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="G:\AutoAI_01\google_chrome_profile"
echo [3/3] Starting Python Core Server...
call venv\Scripts\activate
python main.py
echo.
echo Server stopped. Press any key to return...
pause >nul
goto menu

:start_server
echo.
echo Starting Python Core Server...
call venv\Scripts\activate
python main.py
echo.
pause >nul
goto menu

:reset_chrome
echo.
echo Terminating all Chrome processes...
taskkill /f /im chrome.exe /t >nul 2>&1
echo Relaunching isolated Chrome...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="G:\AutoAI_01\google_chrome_profile"
echo Chrome reset complete!
pause >nul
goto menu

:clean_logs
echo.
if exist "logs\sys_logs.log" (
    type nul > "logs\sys_logs.log"
    echo Log file cleared!
) else (
    echo Log file not found.
)
pause >nul
goto menu

:reset_queue
echo.
if exist "queue_backup.json" (
    del /q "queue_backup.json"
    echo Queue cache cleared!
) else (
    echo No queue records found.
)
pause >nul
goto menu

:backup_db
echo.
if not exist "history.db" (
    echo history.db not found.
    pause >nul
    goto menu
)
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set ts=%datetime:~0,14%
copy "history.db" "history_backup_%ts%.db" >nul
echo Database backed up: history_backup_%ts%.db
pause >nul
goto menu

:open_downloads
echo.
if not exist "Downloads" mkdir "Downloads"
start "" "Downloads"
goto menu

:kill_all
echo.
echo Executing Ghost Kill...
taskkill /f /im chrome.exe /t >nul 2>&1
taskkill /f /im python.exe /t >nul 2>&1
echo All automation processes terminated!
pause >nul
goto menu

:venv_shell
echo.
echo Opening command prompt with Venv activated...
start cmd /k "cd /d G:\AutoAI_01 && call venv\Scripts\activate && echo [Venv] Environment is now active. You can run python scripts here."
goto menu