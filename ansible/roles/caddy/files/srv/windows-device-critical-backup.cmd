@echo off
setlocal

:: ======================================================================
:: RESTIC WINDOWS BACKUP SCRIPT (ULTIMATE EDITION)
:: ======================================================================
:: INSTRUCTIONS:
:: 1. Download restic.exe for Windows from https://github.com/restic/restic/releases
:: 2. Place restic.exe in C:\Backup
:: 3. (Optional) Create an excludes.txt file in C:\Backup to ignore certain files.
:: 4. Update the variables in "STEP 1: MANDATORY CONFIGURATION" below.
:: 5. Open Windows Task Scheduler (taskschd.msc):
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
:: IMPORTANT NOTE ON SPECIAL CHARACTERS IN URL: 
:: If your 'htpasswd_password' contains special characters (like @, #, ?), 
:: they MUST be URL-encoded (e.g., @ becomes %40, # becomes %23).
set "RESTIC_REPOSITORY=rest:http://authelia_backup_user:authelia_backup_password@<server>/authelia_backup_user/critical"

:: 2. What is the encryption password for this backup?
:: Do NOT URL-encode this password. Just type it normally.
set "RESTIC_PASSWORD=password"

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
