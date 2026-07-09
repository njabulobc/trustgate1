@echo off
REM Windows shim: runs start.ps1 using PowerShell with an execution policy bypass so users can double-click this .bat
SETLOCAL
SET scriptPath=%~dp0start.ps1
IF NOT EXIST "%scriptPath%" (
  echo start.ps1 not found in %~dp0
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%scriptPath%"
ENDLOCAL