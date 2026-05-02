# HMA App - phone/device verification setup for Windows
# Use this for Docker + HTTPS verification on phones or tablets.

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== HMA Device Verification Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check Docker is running
try {
    docker info 2>&1 | Out-Null
} catch {
    Write-Host "ERROR: Docker Desktop is not running." -ForegroundColor Red
    Write-Host "Start Docker Desktop and run this script again."
    pause
    exit 1
}

# Create .env from example if not present
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env file created from template." -ForegroundColor Green
}

$envContent = Get-Content ".env" -Raw

# Keep the shared DATA_DIR portable between local dev and Docker.
if ($envContent -match '(?m)^DATA_DIR=/app/data\s*$') {
    $envContent = $envContent -replace '(?m)^DATA_DIR=/app/data\s*$', 'DATA_DIR=./data'
    [System.IO.File]::WriteAllText((Resolve-Path ".env").Path, $envContent)
    Write-Host "DATA_DIR updated to ./data for shared local + Docker use." -ForegroundColor Green
}

# Prompt for PIN if not already set
$envContent = Get-Content ".env" -Raw
$pinIsEmpty = $envContent -match 'ACCESS_PIN=\s*[\r\n]' -or $envContent -match 'ACCESS_PIN=\s*$'
if ($pinIsEmpty) {
    Write-Host ""
    $pin = Read-Host "Set an access PIN for the app (workers will enter this to log in)"
    if ($pin) {
        $envContent = $envContent -replace 'ACCESS_PIN=.*', "ACCESS_PIN=$pin"
        [System.IO.File]::WriteAllText((Resolve-Path ".env").Path, $envContent)
        Write-Host "PIN saved." -ForegroundColor Green
    } else {
        Write-Host "No PIN set - the app will be accessible without authentication." -ForegroundColor Yellow
    }
}

# Build and start
Write-Host ""
Write-Host "Building and starting HMA App (this may take a few minutes on first run)..." -ForegroundColor Cyan
docker compose up --build -d

Write-Host ""
Write-Host "=== App is running ===" -ForegroundColor Green
Write-Host ""

Write-Host "This workflow is for phone/device verification over Docker + HTTPS." -ForegroundColor Cyan
Write-Host "For day-to-day coding on this machine, use the local dev workflow:" -ForegroundColor White
Write-Host "  backend: uvicorn api.app.main:app --reload --port 8002" -ForegroundColor Yellow
Write-Host "  frontend: cd web && npm run dev" -ForegroundColor Yellow
Write-Host "  browser:  http://localhost:5181" -ForegroundColor Yellow
Write-Host ""

# Show LAN IP addresses
Write-Host "Workers should open one of these addresses on their phone browser:" -ForegroundColor Cyan
$ips = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notmatch '^127\.' -and $_.IPAddress -notmatch '^169\.' } |
    Select-Object -ExpandProperty IPAddress
foreach ($ip in $ips) {
    Write-Host "  https://$ip" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "NOTE: Phones will show a 'Not secure' warning on first visit." -ForegroundColor White
Write-Host "Workers should tap:  Advanced -> Proceed to [IP] (unsafe)" -ForegroundColor White
Write-Host ""
Write-Host "To stop the app:  docker compose down"
Write-Host "To view logs:     docker compose logs -f"
Write-Host ""
pause
