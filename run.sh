#!/usr/bin/env bash
set -euo pipefail

echo ""
echo " ========================================="
echo "  PDF Counsel"
echo " ========================================="
echo ""

# ── 1. Ensure .env exists ──────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp ".env.example" ".env"
    else
        printf "OPENAI_API_KEY=sk-...\nOPENAI_MODEL=gpt-4o-mini\n" > ".env"
    fi
    echo " [setup] .env file created."
fi

if grep -q "sk-\.\.\." ".env" || ! grep -q "OPENAI_API_KEY" ".env"; then
    echo ""
    echo " [warning] No OpenAI API key found in .env."
    echo "   The app will start but chat will not work until you add one."
    echo "   Edit .env, set OPENAI_API_KEY=sk-..., then restart."
    echo ""
fi

# ── 2. Check Python ────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo " [error] Python 3 was not found."
    echo ""
    echo " Please install Python 3.11 or newer:"
    echo "   macOS:  brew install python  or  https://www.python.org/downloads/"
    echo "   Linux:  sudo apt install python3 python3-venv"
    echo ""
    exit 1
fi

# ── 3. Create venv and install backend deps (first run only) ───────────────────
if [ ! -f ".venv/bin/python" ]; then
    echo " [setup] First run - setting up Python environment..."
    echo " This takes about a minute. Please wait."
    echo ""
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt --quiet
    echo " [setup] Backend ready."
    echo ""
fi

# ── 4. Check Node ──────────────────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
    echo " [error] Node.js was not found."
    echo ""
    echo " Please install Node.js (LTS) from: https://nodejs.org"
    echo ""
    exit 1
fi

# ── 5. Install frontend deps (first run only) ──────────────────────────────────
if [ ! -d "frontend/node_modules" ]; then
    echo " [setup] First run - installing frontend dependencies..."
    echo " This takes about a minute. Please wait."
    echo ""
    (cd frontend && npm install --silent)
    echo " [setup] Frontend ready."
    echo ""
fi

# ── 6. Start backend ───────────────────────────────────────────────────────────
echo " Starting..."
.venv/bin/python -m uvicorn backend.main:app &
BACKEND_PID=$!
sleep 2

# ── 7. Start frontend ──────────────────────────────────────────────────────────
(cd frontend && npm run dev) &
FRONTEND_PID=$!
sleep 3

# ── 8. Open browser ────────────────────────────────────────────────────────────
if command -v open &>/dev/null; then
    open http://localhost:5173          # macOS
elif command -v xdg-open &>/dev/null; then
    xdg-open http://localhost:5173      # Linux
fi

echo ""
echo " ========================================="
echo "  PDF Counsel is running!"
echo ""
echo "  Your browser should open automatically."
echo "  If not, go to:  http://localhost:5173"
echo ""
echo "  Press Ctrl+C to stop the app."
echo " ========================================="
echo ""

# Keep script alive; shut down both servers on Ctrl+C
trap "echo ''; echo ' Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
