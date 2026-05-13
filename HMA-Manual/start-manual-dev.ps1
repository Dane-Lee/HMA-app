# HMA-Manual one-window development startup.
# Starts the manual FastAPI backend and manual Vite frontend together.

[CmdletBinding()]
param(
    [int]$BackendPort = 8003,
    [int]$FrontendPort = 5182,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Test-LocalPort {
    param([int]$PortToCheck)
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $PortToCheck)
        if (-not $task.Wait(300)) { return $false }
        return $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-ForPort {
    param([int]$PortToCheck, [string]$Name, [int]$TimeoutSeconds = 45)
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
    param([System.Diagnostics.Process]$Process, [string]$Name)
    if ($null -eq $Process) { return }
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

if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: python was not found." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: npm was not found." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".env.manual") -and (Test-Path ".env.manual.example")) {
    Copy-Item ".env.manual.example" ".env.manual"
    Write-Host ".env.manual file created from .env.manual.example." -ForegroundColor Green
}

if (Test-LocalPort $BackendPort -or Test-LocalPort $FrontendPort) {
    Write-Host "One HMA-Manual port is already in use. Backend: $BackendPort Frontend: $FrontendPort" -ForegroundColor Red
    exit 1
}

Push-Location "web_manual"
try {
    if (-not (Test-Path "node_modules")) {
        Write-Host "Installing HMA-Manual frontend packages first..."
        npm install
    }
} finally {
    Pop-Location
}

$python = (Get-Command "python").Source
$npmCommand = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
if (-not $npmCommand) { $npmCommand = Get-Command "npm" }

$backendOut = Join-Path $PSScriptRoot "manual-backend-dev.out.log"
$backendErr = Join-Path $PSScriptRoot "manual-backend-dev.err.log"
$frontendOut = Join-Path $PSScriptRoot "manual-frontend-dev.out.log"
$frontendErr = Join-Path $PSScriptRoot "manual-frontend-dev.err.log"
$backend = $null
$frontend = $null
$url = "http://localhost:$FrontendPort"

try {
    Write-Host "Starting HMA-Manual backend and frontend..." -ForegroundColor Cyan
    $backend = Start-Process `
        -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "api_manual.app.main:app", "--reload", "--port", "$BackendPort") `
        -WorkingDirectory $PSScriptRoot `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr

    $frontend = Start-Process `
        -FilePath $npmCommand.Source `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
        -WorkingDirectory (Join-Path $PSScriptRoot "web_manual") `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $frontendOut `
        -RedirectStandardError $frontendErr

    if (-not (Wait-ForPort $BackendPort "HMA-Manual backend")) {
        throw "Manual backend did not start. Check manual-backend-dev.err.log."
    }
    if (-not (Wait-ForPort $FrontendPort "HMA-Manual frontend")) {
        throw "Manual frontend did not start. Check manual-frontend-dev.err.log."
    }

    Write-Host "HMA-Manual is running at $url" -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process $url }
    Write-Host "Keep this window open. Press Enter here to stop both servers."
    [void][Console]::ReadLine()
} finally {
    Stop-ProcessTree $frontend "HMA-Manual frontend"
    Stop-ProcessTree $backend "HMA-Manual backend"
}
