@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%setup_hwp_automation.ps1"

if not exist "%PS_SCRIPT%" (
  echo [ERROR] setup_hwp_automation.ps1 not found.
  echo Expected: "%PS_SCRIPT%"
  pause
  exit /b 1
)

set "DLL_PATH="

for /f "delims=" %%I in ('dir /b /s "%USERPROFILE%\Downloads\FilePathCheckerModuleExample.dll" 2^>nul') do (
  if not defined DLL_PATH set "DLL_PATH=%%I"
)

if not defined DLL_PATH (
  echo.
  echo Could not auto-find FilePathCheckerModuleExample.dll under Downloads.
  set /p DLL_PATH=Enter full DLL path: 
)

if not exist "%DLL_PATH%" (
  echo [ERROR] DLL file not found:
  echo "%DLL_PATH%"
  pause
  exit /b 1
)

echo.
echo [INFO] Running one-click HWP automation setup...
echo DLL: "%DLL_PATH%"
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" -ModuleDllPath "%DLL_PATH%" -Scope CurrentUser -VerifyCom
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
  echo [DONE] Security module registration completed.
) else (
  echo [FAILED] Setup failed. Exit code: %EXIT_CODE%
)
echo.
pause
exit /b %EXIT_CODE%
