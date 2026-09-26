@echo off
setlocal

:: ======================================================================
:: RESTIC WINDOWS BACKUP SCRIPT
:: ======================================================================
:: INSTRUCTIONS:
:: 1. Download restic.exe from https://github.com/restic/restic/releases
:: 2. Place restic.exe in C:\Backup
:: 3. (Optional) Create an excludes.txt file in C:\Backup to ignore certain files.
:: 4. Create two one-line files in C:\Backup and restrict them to your account:
::      restic-password.txt  - the repository encryption password
::      rest-password.txt    - your backup account's login password
::    icacls C:\Backup\restic-password.txt /inheritance:r /grant:r "%USERNAME%:R"
::    icacls C:\Backup\rest-password.txt   /inheritance:r /grant:r "%USERNAME%:R"
:: 5. Update the variables in "STEP 1: MANDATORY CONFIGURATION" below.
:: 6. FIRST RUN ONLY: run this script once with INIT_REPO=1 set in CMD:
::      set INIT_REPO=1 && C:\Backup\windows-device-critical-backup.cmd
:: 7. Open Windows Task Scheduler (taskschd.msc):
::    - Create Basic Task -> "Daily Restic Backup" -> Set your preferred time.
::    - Action: Start a program -> Point to this .cmd file.
::    - Check "Open the Properties dialog for this task when I click Finish".
::    - In Properties:
::      a) Change user account to your personal account (NOT SYSTEM).
::      b) Check "Run whether user is logged on or not" (Hides the CMD window).
::      c) Check "Run with highest privileges" (Required for VSS / locked files).
::    Task Scheduler's "Last Run Result" shows 0x0 on success, 0x3 when some
::    files were skipped, anything else on failure.
:: ======================================================================

:: ==========================================
:: STEP 1: MANDATORY CONFIGURATION
:: ==========================================

:: 1. Where is the backup server? No credentials in the URL.
:: CHOOSE YOUR STORAGE TIER BY CHANGING THE URL PATH:
:: - /<backup_user>/cloud/<device_name> -> Synced to cloud storage
:: - /<backup_user>/local/<device_name> -> Stays on the home server only
set "RESTIC_REPOSITORY=rest:https://<server>/<backup_user>/cloud/MyPC"
set "RESTIC_REST_USERNAME=<backup_user>"

:: 2. Secret files (see instruction 4). Lose the restic password and the
:: backup cannot be restored by anyone.
set "RESTIC_PASSWORD_FILE=C:\Backup\restic-password.txt"
set "REST_PASSWORD_FILE=C:\Backup\rest-password.txt"

:: 3. What folders do you want to backup? (Separate multiple paths with spaces)
:: WARNING: Always use absolute paths (C:\Users\...) instead of %USERPROFILE%.
set INCLUDE_DIR="C:\Users\YourUsername\Documents" "C:\Users\YourUsername\Desktop\ImportantFolder"


:: ==========================================
:: STEP 2: ADVANCED CONFIGURATION (Paths)
:: ==========================================
set "RESTIC_EXE=C:\Backup\restic.exe"
set "LOG_FILE=C:\Backup\backup_log.txt"
set "EXCLUDE_FILE=C:\Backup\excludes.txt"


:: ==========================================
:: STEP 3: PRE-FLIGHT CHECK
:: ==========================================
echo [%date% %time%] === BACKUP START === >> "%LOG_FILE%"

if not exist "%RESTIC_PASSWORD_FILE%" (
    echo [%date% %time%] [CRITICAL ERROR] %RESTIC_PASSWORD_FILE% not found. >> "%LOG_FILE%"
    exit /b 1
)
if not exist "%REST_PASSWORD_FILE%" (
    echo [%date% %time%] [CRITICAL ERROR] %REST_PASSWORD_FILE% not found. >> "%LOG_FILE%"
    exit /b 1
)
set /p RESTIC_REST_PASSWORD=<"%REST_PASSWORD_FILE%"

echo "%RESTIC_REPOSITORY% %RESTIC_REST_USERNAME%" | findstr /C:"<server>" /C:"<backup_user>" >nul
if %ERRORLEVEL% EQU 0 (
    echo [%date% %time%] [CRITICAL ERROR] Configuration still contains template placeholders. >> "%LOG_FILE%"
    exit /b 1
)

if "%INIT_REPO%"=="1" (
    echo [%date% %time%] Initialising repository... >> "%LOG_FILE%"
    "%RESTIC_EXE%" init >> "%LOG_FILE%" 2>&1
    exit /b
)

"%RESTIC_EXE%" cat config >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] [CRITICAL ERROR] Repository missing, server unreachable, or a password is wrong. >> "%LOG_FILE%"
    exit /b 1
)


:: ==========================================
:: STEP 4: MAIN BACKUP PROCESS
:: ==========================================
set "EXCLUDE_FLAG="
if exist "%EXCLUDE_FILE%" set EXCLUDE_FLAG=--exclude-file="%EXCLUDE_FILE%"

"%RESTIC_EXE%" backup %INCLUDE_DIR% %EXCLUDE_FLAG% --use-fs-snapshot --compression max --verbose >> "%LOG_FILE%" 2>&1
set "BACKUP_RC=%ERRORLEVEL%"

if "%BACKUP_RC%"=="3" echo [%date% %time%] [WARNING] Snapshot created, but some files could not be read. >> "%LOG_FILE%"
if not "%BACKUP_RC%"=="0" if not "%BACKUP_RC%"=="3" (
    echo [%date% %time%] [CRITICAL ERROR] Backup failed with exit code %BACKUP_RC%. No snapshot was created. >> "%LOG_FILE%"
    exit /b %BACKUP_RC%
)


:: ==========================================
:: STEP 5: RETENTION POLICY
:: ==========================================
"%RESTIC_EXE%" forget --prune --keep-daily 7 --keep-weekly 4 --keep-monthly 6 >> "%LOG_FILE%" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] [WARNING] Retention failed. Backup itself succeeded. >> "%LOG_FILE%"
)

echo [%date% %time%] === BACKUP FINISHED (exit %BACKUP_RC%) === >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"
endlocal & exit /b %BACKUP_RC%
