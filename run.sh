#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[setup]${NC} $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $*"; }
error()   { echo -e "${RED}[error]${NC} $*"; exit 1; }

# ── helpers ───────────────────────────────────────────────────────────────────
setup_venv() {
    local dir="$1"
    if [ ! -d "$REPO_ROOT/$dir/venv" ]; then
        info "Creating venv for $dir ..."
        python3 -m venv "$REPO_ROOT/$dir/venv"
        "$REPO_ROOT/$dir/venv/bin/pip" install --quiet -r "$REPO_ROOT/$dir/requirements.txt"
        info "$dir — dependencies installed."
    else
        info "$dir — venv already exists, skipping."
    fi
}

# ── checks ────────────────────────────────────────────────────────────────────
command -v python3 >/dev/null 2>&1 || error "python3 not found. Install Python 3.11+."
command -v node    >/dev/null 2>&1 || error "node not found. Install Node.js 18+."
command -v npm     >/dev/null 2>&1 || error "npm not found."

# ── .env setup ────────────────────────────────────────────────────────────────
ENV_FILE="$REPO_ROOT/orchestrator/.env"
if [ ! -f "$ENV_FILE" ]; then
    cp "$REPO_ROOT/orchestrator/.env.example" "$ENV_FILE"
    # Auto-fill APP_ROOT with the actual repo path
    sed -i "s|APP_ROOT=.*|APP_ROOT=$REPO_ROOT|" "$ENV_FILE"
    warn ".env created from example. Fill in GEMINI_API_KEY (or Ollama settings) before running."
    warn "Edit: $ENV_FILE"
    echo ""
    read -rp "Press Enter once you've configured .env, or Ctrl+C to abort ..."
    echo ""
else
    # Make sure APP_ROOT is set to current location
    sed -i "s|APP_ROOT=.*|APP_ROOT=$REPO_ROOT|" "$ENV_FILE"
    info ".env found — APP_ROOT updated to $REPO_ROOT."
fi

# ── mcp-config.json setup ─────────────────────────────────────────────────────
MCP_CONFIG="$REPO_ROOT/orchestrator/mcp-config.json"
if [ ! -f "$MCP_CONFIG" ]; then
    cp "$REPO_ROOT/orchestrator/mcp-config.json.example" "$MCP_CONFIG"
    info "mcp-config.json created from example."
fi

# ── Python venvs ──────────────────────────────────────────────────────────────
setup_venv "mcp-monai"
setup_venv "mcp-radlex"
setup_venv "mcp-utils"
setup_venv "mcp-skills"
setup_venv "orchestrator"

# ── Frontend deps ─────────────────────────────────────────────────────────────
if [ ! -d "$REPO_ROOT/frontend/node_modules" ]; then
    info "Installing frontend dependencies ..."
    npm --prefix "$REPO_ROOT/frontend" install --silent
    info "Frontend dependencies installed."
else
    info "Frontend node_modules already exists, skipping."
fi

# ── Sample data ───────────────────────────────────────────────────────────────
SAMPLE_EXAMS="$REPO_ROOT/orchestrator/sample_data/exams"
if [ ! -d "$SAMPLE_EXAMS" ] || [ -z "$(find "$SAMPLE_EXAMS" -type f -name '*.dcm' -print -quit 2>/dev/null || true)" ]; then
    info "Downloading sample CT data from TCIA..."
    "$REPO_ROOT/orchestrator/venv/bin/python" "$REPO_ROOT/orchestrator/sample_data/download_sample_data.py"
else
    info "Sample CT data already present, skipping download."
fi

# ── Launch ────────────────────────────────────────────────────────────────────
cleanup() {
    echo ""
    info "Shutting down ..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup SIGINT SIGTERM

info "Starting backend  → http://localhost:5001  (docs: http://localhost:5001/docs)"
"$REPO_ROOT/orchestrator/venv/bin/python" "$REPO_ROOT/orchestrator/backend.py" &
BACKEND_PID=$!

info "Starting frontend → http://localhost:5173"
npm --prefix "$REPO_ROOT/frontend" run dev -- --host 0.0.0.0 &
FRONTEND_PID=$!

info "Both services running. Press Ctrl+C to stop."
wait "$BACKEND_PID" "$FRONTEND_PID"
