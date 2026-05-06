$Root = $PSScriptRoot

Write-Host ""
Write-Host " ========================================="
Write-Host "   PDF Counsel"
Write-Host " ========================================="
Write-Host ""

# ── 1. Ensure .env exists ─────────────────────────────────────────────────────
$EnvFile = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"

if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
    } else {
        Set-Content $EnvFile "OPENAI_API_KEY=sk-...`nOPENAI_MODEL=gpt-4o-mini"
    }
    Write-Host " [setup] .env file created."
}

$EnvContent = Get-Content $EnvFile -Raw
if ($EnvContent -match "OPENAI_API_KEY=sk-\.\.\." -or $EnvContent -notmatch "OPENAI_API_KEY") {
    Write-Host ""
    Write-Host " [warning] No OpenAI API key found in .env."
    Write-Host "   The app will start but chat will not work until you add one."
    Write-Host "   Edit .env, set OPENAI_API_KEY=sk-..., then restart."
    Write-Host ""
}

# ── 2. Check Python ───────────────────────────────────────────────────────────
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host " [error] Python was not found."
    Write-Host ""
    Write-Host " Please install Python 3.11 or newer from:"
    Write-Host "   https://www.python.org/downloads/"
    Write-Host " Make sure to tick 'Add Python to PATH' during installation."
    Write-Host ""
    Read-Host " Press ENTER to close"
    exit 1
}

# ── 3. Create venv and install backend deps (first run only) ──────────────────
$Venv = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Venv)) {
    Write-Host " [setup] First run - setting up Python environment..."
    Write-Host " This takes about a minute. Please wait."
    Write-Host ""
    python -m venv (Join-Path $Root ".venv")
    & (Join-Path $Root ".venv\Scripts\pip.exe") install -r (Join-Path $Root "requirements.txt") --quiet
    Write-Host " [setup] Backend ready."
    Write-Host ""
}

# ── 4. Check Node ─────────────────────────────────────────────────────────────
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host " [error] Node.js was not found."
    Write-Host ""
    Write-Host " Please install Node.js from:"
    Write-Host "   https://nodejs.org  (choose the LTS version)"
    Write-Host ""
    Read-Host " Press ENTER to close"
    exit 1
}

# ── 5. Install frontend deps (first run only) ─────────────────────────────────
$NodeModules = Join-Path $Root "frontend\node_modules"
if (-not (Test-Path $NodeModules)) {
    Write-Host " [setup] First run - installing frontend dependencies..."
    Write-Host " This takes about a minute. Please wait."
    Write-Host ""
    Push-Location (Join-Path $Root "frontend")
    npm install --silent
    Pop-Location
    Write-Host " [setup] Frontend ready."
    Write-Host ""
}

# ── 6. Start backend ──────────────────────────────────────────────────────────
Write-Host " Starting backend..."
Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -NoExit -Command `"Set-Location '$Root'; .venv\Scripts\python.exe -m uvicorn backend.main:app`""

Start-Sleep -Seconds 2

# ── 7. Start frontend ─────────────────────────────────────────────────────────
Write-Host " Starting frontend..."
Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -NoExit -Command `"Set-Location '$Root\frontend'; npm run dev`""

Write-Host ""
Write-Host " ========================================="
Write-Host "   PDF Counsel is starting!"
Write-Host ""
Write-Host "   Open your browser at:"
Write-Host "     http://localhost:5173"
Write-Host ""
Write-Host "   To stop, close the backend and"
Write-Host "   frontend PowerShell windows."
Write-Host " ========================================="
Write-Host ""
