# DocuFlow AI — Pre-Push Local Validation Script
Write-Host "=== DocuFlow AI: Running Full Local Validation Suite ===" -ForegroundColor Cyan

# 1. Backend Checks
Write-Host "`n--- [1/2] Running Backend Checks ---" -ForegroundColor Yellow
Set-Location "$PSScriptRoot\..\backend"

if (Test-Path ".venv\Scripts\python.exe") {
    $pytest = ".venv\Scripts\pytest.exe"
    $ruff = ".venv\Scripts\ruff.exe"
    $mypy = ".venv\Scripts\mypy.exe"
    $alembic = ".venv\Scripts\alembic.exe"

    Write-Host "Running Ruff Linting..."
    & $ruff check app tests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "Running Ruff Format Check..."
    & $ruff format --check app tests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "Running Mypy Type Checking..."
    & $mypy app
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "Running Alembic Offline Migration..."
    & $alembic upgrade head --sql | Out-Null
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "Running Pytest Suite..."
    & $pytest --cov=app --cov-report=term-missing
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "Backend .venv not found. Skipping backend checks." -ForegroundColor Red
}

# 2. Frontend Checks
Write-Host "`n--- [2/2] Running Frontend Checks ---" -ForegroundColor Yellow
Set-Location "$PSScriptRoot\..\frontend"

Write-Host "Running Frontend Linter..."
npm run lint
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running Frontend Vitest Suite..."
npm test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Running Next.js Build..."
npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Set-Location "$PSScriptRoot\.."
Write-Host "`n=== ALL VALIDATION CHECKS PASSED SUCCESSFULLY! ===" -ForegroundColor Green
