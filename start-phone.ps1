# HMA App - phone/tablet startup
# Starts Docker Desktop if needed, then runs the existing HTTPS Docker setup.

[CmdletBinding()]
param(
    [int]$WaitSeconds = 180
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Test-DockerRunning {
    try {
        docker info 2>&1 | Out-Null
        return $true
    } catch {
        return $false
    }
}

if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker was not found." -ForegroundColor Red
    Write-Host "Install Docker Desktop, then run this script again." -ForegroundColor Yellow
    pause
    exit 1
}

if (-not (Test-DockerRunning)) {
    Write-Host "Docker Desktop is not running. Starting it now..." -ForegroundColor Cyan

    $dockerDesktopPaths = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Docker\Docker Desktop.exe"
    )
    $dockerDesktop = $dockerDesktopPaths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

    if (-not $dockerDesktop) {
        Write-Host "ERROR: Could not find Docker Desktop." -ForegroundColor Red
        Write-Host "Open Docker Desktop manually, then run .\start-phone.ps1 again." -ForegroundColor Yellow
        pause
        exit 1
    }

    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden

    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerRunning) {
            Write-Host ""
            Write-Host "Docker Desktop is ready." -ForegroundColor Green
            break
        }
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 3
    }

    if (-not (Test-DockerRunning)) {
        Write-Host ""
        Write-Host "ERROR: Docker Desktop did not finish starting within $WaitSeconds seconds." -ForegroundColor Red
        Write-Host "Open Docker Desktop manually, wait until it says it is running, then run this script again." -ForegroundColor Yellow
        pause
        exit 1
    }
}

& (Join-Path $PSScriptRoot "setup.ps1")
