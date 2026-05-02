# HMA App - simple local startup
# Builds the frontend, starts FastAPI, opens the app, and stops it when you press Enter.

[CmdletBinding()]
param(
    [int]$Port = 8002,
    [switch]$SkipBuild,
    [switch]$NoBrowser,
    [switch]$Restart
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Require-Command {
    param(
        [string]$Name,
        [string]$Hint
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: '$Name' was not found." -ForegroundColor Red
        Write-Host $Hint -ForegroundColor Yellow
        exit 1
    }
}

function Test-LocalPort {
    param([int]$PortToCheck)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $PortToCheck)
        if (-not $task.Wait(300)) {
            return $false
        }
        return $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Get-PortProcessIds {
    param([int]$PortToCheck)

    $ids = @()
    $lines = & netstat.exe -ano -p tcp
    foreach ($line in $lines) {
        if ($line -match "^\s*TCP\s+\S+:$PortToCheck\s+\S+\s+LISTENING\s+(\d+)\s*$") {
            $ids += [int]$Matches[1]
        }
    }
    return $ids | Sort-Object -Unique
}

function Stop-PortProcesses {
    param([int]$PortToStop)

    $processIds = Get-PortProcessIds $PortToStop
    if (-not $processIds -or $processIds.Count -eq 0) {
        return
    }

    foreach ($processId in $processIds) {
        if ($processId -eq $PID) {
            continue
        }

        Write-Host "Stopping process $processId on port $PortToStop..."
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
        } catch {
            & taskkill.exe /PID $processId /T /F | Out-Null
        }
    }

    Start-Sleep -Seconds 1
}

function Test-LogoRoute {
    param([int]$AppPort)

    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$AppPort/ati-logo/ATI-logo.png" -UseBasicParsing -TimeoutSec 5
        return ($response.StatusCode -eq 200 -and "$($response.Headers["Content-Type"])" -like "image/png*")
    } catch {
        return $false
    }
}

function Resolve-PythonCommand {
    $venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return (Resolve-Path $venvPython).Path
    }

    Require-Command "python" "Install Python 3.11+, then run this script again."
    return (Get-Command "python").Source
}

function Wait-ForPort {
    param(
        [int]$PortToCheck,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-LocalPort $PortToCheck) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Stop-ProcessTree {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$Name
    )

    if ($null -eq $Process) {
        return
    }

    try {
        $Process.Refresh()
        if (-not $Process.HasExited) {
            Write-Host "Stopping $Name..."
            & taskkill.exe /PID $Process.Id /T /F | Out-Null
        }
    } catch {
        Write-Host "Could not stop $Name automatically. Process ID was $($Process.Id)." -ForegroundColor Yellow
    }
}

Require-Command "npm" "Install Node.js/npm, then run this script again."

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env file created from .env.example." -ForegroundColor Green
}

$url = "http://localhost:$Port"
if (Test-LocalPort $Port) {
    if ($Restart) {
        Write-Host "Restart requested. Stopping the app currently on port $Port..." -ForegroundColor Cyan
        Stop-PortProcesses $Port
    } elseif (Test-LogoRoute $Port) {
        Write-Host "The app is already running on port $Port." -ForegroundColor Yellow
        Write-Host "Opening $url."
        if (-not $NoBrowser) {
            Start-Process $url
        }
        exit 0
    } else {
        Write-Host "Something is already running on port $Port, but it is not serving the app correctly." -ForegroundColor Yellow
        $answer = Read-Host "Stop it and restart the app now? Press Enter for yes, or type N for no"
        if ($answer -match "^[Nn]") {
            Write-Host "Leaving the existing process running. To force a restart later, run: .\start-local.ps1 -Restart"
            exit 1
        }
        Stop-PortProcesses $Port
    }
}

if (-not $SkipBuild) {
    Write-Host ""
    Write-Host "Building the web app..." -ForegroundColor Cyan
    Push-Location "web"
    try {
        if (-not (Test-Path "node_modules")) {
            Write-Host "Installing frontend packages first..."
            npm install
        }
        npm run build
    } finally {
        Pop-Location
    }
}

$python = Resolve-PythonCommand
$stdoutLog = Join-Path $PSScriptRoot "local-app.out.log"
$stderrLog = Join-Path $PSScriptRoot "local-app.err.log"
$server = $null

try {
    Write-Host ""
    Write-Host "Starting HMA App..." -ForegroundColor Cyan
    $server = Start-Process `
        -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "api.app.main:app", "--port", "$Port") `
        -WorkingDirectory $PSScriptRoot `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog

    if (-not (Wait-ForPort $Port)) {
        throw "The app did not start on port $Port. Check local-app.err.log for details."
    }

    Write-Host ""
    Write-Host "HMA App is running at $url" -ForegroundColor Green
    Write-Host "Logs: local-app.out.log and local-app.err.log"
    if (-not $NoBrowser) {
        Start-Process $url
    }

    Write-Host ""
    Write-Host "Keep this window open. Press Enter here to stop the app."
    [void][Console]::ReadLine()
} finally {
    Stop-ProcessTree $server "HMA App"
}
