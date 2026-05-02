# HMA App - one-window development startup
# Starts the FastAPI backend and Vite frontend together, then stops both when you press Enter.

[CmdletBinding()]
param(
    [int]$BackendPort = 8002,
    [int]$FrontendPort = 5181,
    [switch]$NoBrowser
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

function Wait-ForPort {
    param(
        [int]$PortToCheck,
        [string]$Name,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-LocalPort $PortToCheck) {
            Write-Host "$Name is ready on port $PortToCheck." -ForegroundColor Green
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

Require-Command "python" "Install Python 3.11+, then run this script again."
Require-Command "npm" "Install Node.js/npm, then run this script again."

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env file created from .env.example." -ForegroundColor Green
}

$backendRunning = Test-LocalPort $BackendPort
$frontendRunning = Test-LocalPort $FrontendPort
$url = "http://localhost:$FrontendPort"

if ($backendRunning -and $frontendRunning) {
    Write-Host "The development app already appears to be running." -ForegroundColor Yellow
    if (-not $NoBrowser) {
        Start-Process $url
    }
    exit 0
}

if ($backendRunning -or $frontendRunning) {
    Write-Host "One required port is already in use." -ForegroundColor Red
    Write-Host "Backend port $BackendPort in use: $backendRunning"
    Write-Host "Frontend port $FrontendPort in use: $frontendRunning"
    Write-Host "Stop the old process or change ports before running this script."
    exit 1
}

Push-Location "web"
try {
    if (-not (Test-Path "node_modules")) {
        Write-Host "Installing frontend packages first..."
        npm install
    }
} finally {
    Pop-Location
}

$python = (Get-Command "python").Source
$npmCommand = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
if (-not $npmCommand) {
    $npmCommand = Get-Command "npm"
}

$backendOut = Join-Path $PSScriptRoot "backend-dev.out.log"
$backendErr = Join-Path $PSScriptRoot "backend-dev.err.log"
$frontendOut = Join-Path $PSScriptRoot "frontend-dev.out.log"
$frontendErr = Join-Path $PSScriptRoot "frontend-dev.err.log"
$backend = $null
$frontend = $null

try {
    Write-Host ""
    Write-Host "Starting backend and frontend..." -ForegroundColor Cyan
    $backend = Start-Process `
        -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "api.app.main:app", "--reload", "--port", "$BackendPort") `
        -WorkingDirectory $PSScriptRoot `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr

    $frontend = Start-Process `
        -FilePath $npmCommand.Source `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
        -WorkingDirectory (Join-Path $PSScriptRoot "web") `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $frontendOut `
        -RedirectStandardError $frontendErr

    if (-not (Wait-ForPort $BackendPort "Backend")) {
        throw "Backend did not start. Check backend-dev.err.log."
    }
    if (-not (Wait-ForPort $FrontendPort "Frontend")) {
        throw "Frontend did not start. Check frontend-dev.err.log."
    }

    Write-Host ""
    Write-Host "Development app is running at $url" -ForegroundColor Green
    Write-Host "Logs: backend-dev.*, frontend-dev.*"
    if (-not $NoBrowser) {
        Start-Process $url
    }

    Write-Host ""
    Write-Host "Keep this window open. Press Enter here to stop both servers."
    [void][Console]::ReadLine()
} finally {
    Stop-ProcessTree $frontend "frontend"
    Stop-ProcessTree $backend "backend"
}
