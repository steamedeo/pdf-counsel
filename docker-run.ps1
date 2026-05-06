$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

Write-Host ""
Write-Host " ========================================="
Write-Host "  PDF Counsel (Docker)"
Write-Host " ========================================="
Write-Host ""

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host " [error] Docker not found."
    Write-Host " Install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    Write-Host ""
    Read-Host " Press ENTER to close"
    exit 1
}

docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host " [error] Docker is not running."
    Write-Host " Please start Docker Desktop and try again."
    Write-Host ""
    Read-Host " Press ENTER to close"
    exit 1
}

Write-Host " Building and starting PDF Counsel..."
Write-Host " (First run takes a few minutes while Docker builds the images)"
Write-Host ""

Set-Location $Root
docker compose up --build -d

Write-Host ""
Write-Host " ========================================="
Write-Host "  PDF Counsel is running!"
Write-Host ""
Write-Host "  Open your browser at: http://localhost"
Write-Host ""
Write-Host "  To stop:      docker compose down"
Write-Host "  To view logs: docker compose logs -f"
Write-Host " ========================================="
Write-Host ""

Start-Sleep -Seconds 2
Start-Process "http://localhost"
