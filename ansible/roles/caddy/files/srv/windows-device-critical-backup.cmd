@echo off
setlocal

:: ======================================================================
:: RESTIC WINDOWS BACKUP SCRIPT
:: ======================================================================
:: INSTRUCTIONS:
:: 1. Download restic.exe for Windows from https://github.com/restic/restic/releases
:: 2. Place restic.exe in C:\Backup
:: 3. (Optional) Create an excludes.txt file in C:\Backup to ignore certain files.
:: 4. Update the variables in "STEP 1: MANDATORY CONFIGURATION" below.
:: 5. FIRST RUN ONLY: create the password file from step 1.2, then in CMD set the
::    same RESTIC_REPOSITORY and RESTIC_PASSWORD_FILE and run: C:\Backup\restic.exe init
:: 6. Open Windows Task Scheduler (taskschd.msc):
::    - Create Basic Task -> "Daily Restic Backup" -> Set your preferred time.
::    - Action: Start a program -> Point to this .cmd file.
::    - Check "Open the Properties dialog for this task when I click Finish".
::    - In Properties:
::      a) Change user account to your personal account (NOT SYSTEM).
::      b) Check "Run whether user is logged on or not" (Hides the CMD window).
::      c) Check "Run with highest privileges" (Required for VSS / locked files).
:: ======================================================================

:: ==========================================
:: STEP 1: MANDATORY CONFIGURATION
:: ==========================================

:: 1. Where is the backup server?
:: CHOOSE YOUR STORAGE TIER BY CHANGING THE URL PATH:
:: - /authelia_backup_user/cloud/<device_name> -> Synced to cloud storage
:: - /authelia_backup_user/local/<device_name> -> Stays on the home server only
::
:: IMPORTANT NOTE ON SPECIAL CHARACTERS IN URL:
:: If your password contains special characters (like @, #, ?),
:: they MUST be URL-encoded (e.g., @ becomes %40, # becomes %23).
set "RESTIC_REPOSITORY=rest:https://authelia_backup_user:authelia_backup_password@<server>/authelia_backup_user/cloud/MyPC"

:: 2. Where is the encryption password for this backup?
:: Put ONLY the password in this file (one line, not URL-encoded) and
:: restrict it to your account: icacls C:\Backup\restic-password.txt /inheritance:r /grant:r "%USERNAME%:R"
:: Lose this password and the backup cannot be restored by anyone.
set "RESTIC_PASSWORD_FILE=C:\Backup\restic-password.txt"

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
echo [%date% %time%] Checking configuration... >> "%LOG_FILE%"

if not exist "%RESTIC_PASSWORD_FILE%" (
    echo [%date% %time%] [CRITICAL ERROR] Password file %RESTIC_PASSWORD_FILE% not found. >> "%LOG_FILE%"
    echo [%date% %time%] === BACKUP ABORTED === >> "%LOG_FILE%"
    exit /b 1
)

echo "%RESTIC_REPOSITORY%" | findstr /C:"<server>" /C:"authelia_backup_password" >nul
if %ERRORLEVEL% EQU 0 (
    echo [%date% %time%] [CRITICAL ERROR] RESTIC_REPOSITORY still contains the template placeholders. >> "%LOG_FILE%"
    echo [%date% %time%] === BACKUP ABORTED === >> "%LOG_FILE%"
    exit /b 1
)

echo [%date% %time%] Checking rest-server repository availability... >> "%LOG_FILE%"

"%RESTIC_EXE%" snapshots >nul 2>&1

if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] [CRITICAL ERROR] Repository does not exist, rest-server is unresponsive, or password is incorrect! >> "%LOG_FILE%"
    echo [%date% %time%] === BACKUP ABORTED === >> "%LOG_FILE%"
    exit /b 1
)

echo [%date% %time%] Repository responded correctly. >> "%LOG_FILE%"


:: ==========================================
:: STEP 4: MAIN BACKUP PROCESS
:: ==========================================
echo [%date% %time%] Starting data upload... >> "%LOG_FILE%"

set "EXCLUDE_FLAG="
if exist "%EXCLUDE_FILE%" (
    set EXCLUDE_FLAG=--exclude-file="%EXCLUDE_FILE%"
    echo [%date% %time%] Found exclude file. Applying exclusions. >> "%LOG_FILE%"
)

"%RESTIC_EXE%" backup %INCLUDE_DIR% %EXCLUDE_FLAG% --use-fs-snapshot --compression max --verbose >> "%LOG_FILE%" 2>&1

if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] [WARNING] Errors occurred during backup (check logs above). This might happen if a file is heavily locked. >> "%LOG_FILE%"
) else (
    echo [%date% %time%] Data upload completed successfully. >> "%LOG_FILE%"
)


:: ==========================================
:: STEP 5: RETENTION POLICY
:: ==========================================
echo [%date% %time%] Starting retention policy (prune)... >> "%LOG_FILE%"

"%RESTIC_EXE%" forget --prune --keep-daily 7 --keep-weekly 4 --keep-monthly 6 >> "%LOG_FILE%" 2>&1

echo [%date% %time%] === BACKUP FINISHED === >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

endlocal
