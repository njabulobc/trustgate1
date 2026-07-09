# PowerShell portable starter
# Place this file in the project root and double-click start.bat (or run this .ps1) to open terminals for backend and frontend.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# Find virtualenv dir (look for .venv, venv, env)
$venvCandidates = @('.venv','venv','env')
$venv = $null
foreach ($d in $venvCandidates) {
    $act = Join-Path $root "$d\Scripts\Activate.ps1"
    if (Test-Path $act) { $venv = $d; break }
}

function Quote([string]$s) { return '"' + $s + '"' }

# Build activation prefix if venv found
$activatePrefix = ''
if ($venv) { $activatePrefix = ". `"$root\$venv\Scripts\Activate.ps1`"; " }

# Determine backend start command (common patterns)
if (Test-Path (Join-Path $root 'manage.py')) {
    $backendCmd = "$activatePrefix cd `"$root`"; python manage.py runserver 0.0.0.0:8000"
} else {
    # Try to detect FastAPI by searching for files that reference FastAPI
    $fast = Get-ChildItem -Path $root -Recurse -Include *.py -ErrorAction SilentlyContinue |
            Select-String -Pattern 'from\s+fastapi\s+import\s+FastAPI|FastAPI\s*\(' -List | Select-Object -First 1
    if ($fast) {
        # Convert the file path to a python module path (relative to project root)
        $relative = $fast.Path.Substring($root.Length + 1) -replace '\\','.' -replace '\.py$',''
        $backendCmd = "$activatePrefix cd `"$root`"; python -m uvicorn $relative:app --reload --port 8000"
    } elseif (Test-Path (Join-Path $root 'main.py')) {
        $backendCmd = "$activatePrefix cd `"$root`"; python -m uvicorn main:app --reload --port 8000"
    } elseif (Test-Path (Join-Path $root 'app.py')) {
        $backendCmd = "$activatePrefix cd `"$root`"; python -m uvicorn app:app --reload --port 8000"
    } else {
        $backendCmd = "cd `"$root`"; echo 'No recognized backend start command found; close this window after inspecting'; pause"
    }
}

# Start backend in a new PowerShell window (activation is included in the command if available)
Start-Process powershell -ArgumentList "-NoExit","-Command",$backendCmd -WorkingDirectory $root

# Frontend detection and commands
$frontendDir = $null
if (Test-Path (Join-Path $root 'frontend\package.json')) { $frontendDir = Join-Path $root 'frontend' }
elseif (Test-Path (Join-Path $root 'package.json')) { $frontendDir = $root }

if ($frontendDir) {
    $installCmd = "cd `"$frontendDir`"; npm install --no-audit --no-fund"
    $runCmd = "cd `"$frontendDir`"; npm run dev 2>$null || npm start 2>$null; pause"
    # Open terminal to run install (so user can see progress) then run dev server in a separate terminal
    Start-Process powershell -ArgumentList "-NoExit","-Command",$installCmd -WorkingDirectory $frontendDir
    Start-Sleep -Seconds 1
    Start-Process powershell -ArgumentList "-NoExit","-Command",$runCmd -WorkingDirectory $frontendDir
} else {
    Write-Host "No frontend package.json found. Skipping frontend start."
}

Write-Host "Launched backend and frontend terminal(s)."