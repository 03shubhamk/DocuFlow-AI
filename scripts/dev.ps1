# ==============================================================================
# DocuFlow AI — PowerShell Developer Helper Script
# ==============================================================================
param (
    [Parameter(Position = 0)]
    [ValidateSet("up", "down", "restart", "logs", "build", "test", "lint", "format", "migrate", "help")]
    [string]$Command = "help"
)

switch ($Command) {
    "up" {
        Write-Host "Starting DocuFlow AI services with Docker Compose..." -ForegroundColor Cyan
        docker compose up -d
    }
    "down" {
        Write-Host "Stopping DocuFlow AI services..." -ForegroundColor Cyan
        docker compose down
    }
    "restart" {
        Write-Host "Restarting containers..." -ForegroundColor Cyan
        docker compose restart
    }
    "logs" {
        docker compose logs -f
    }
    "build" {
        Write-Host "Building Docker images..." -ForegroundColor Cyan
        docker compose build
    }
    "test" {
        Write-Host "Running Backend Tests..." -ForegroundColor Cyan
        Set-Location "$PSScriptRoot\..\backend"
        pytest -v
        Write-Host "Running Frontend Tests..." -ForegroundColor Cyan
        Set-Location "$PSScriptRoot\..\frontend"
        npm test
        Set-Location "$PSScriptRoot\.."
    }
    "lint" {
        Write-Host "Linting Backend..." -ForegroundColor Cyan
        Set-Location "$PSScriptRoot\..\backend"
        ruff check .
        Write-Host "Linting Frontend..." -ForegroundColor Cyan
        Set-Location "$PSScriptRoot\..\frontend"
        npm run lint
        Set-Location "$PSScriptRoot\.."
    }
    "format" {
        Write-Host "Formatting Backend..." -ForegroundColor Cyan
        Set-Location "$PSScriptRoot\..\backend"
        ruff format .
        Write-Host "Formatting Frontend..." -ForegroundColor Cyan
        Set-Location "$PSScriptRoot\..\frontend"
        npm run format
        Set-Location "$PSScriptRoot\.."
    }
    "migrate" {
        Write-Host "Running Alembic Migrations..." -ForegroundColor Cyan
        Set-Location "$PSScriptRoot\..\backend"
        alembic upgrade head
        Set-Location "$PSScriptRoot\.."
    }
    Default {
        Write-Host "DocuFlow AI PowerShell Commands:" -ForegroundColor Yellow
        Write-Host "  .\scripts\dev.ps1 up      - Start Docker Compose services"
        Write-Host "  .\scripts\dev.ps1 down    - Stop services"
        Write-Host "  .\scripts\dev.ps1 restart - Restart containers"
        Write-Host "  .\scripts\dev.ps1 logs    - Follow logs"
        Write-Host "  .\scripts\dev.ps1 build   - Build images"
        Write-Host "  .\scripts\dev.ps1 test    - Run all tests"
        Write-Host "  .\scripts\dev.ps1 lint    - Lint backend and frontend"
        Write-Host "  .\scripts\dev.ps1 format  - Format backend and frontend"
        Write-Host "  .\scripts\dev.ps1 migrate - Apply database migrations"
    }
}
