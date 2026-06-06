#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  EnterpriseCertIQ — start.sh
#  Starts the full stack locally (Foundry Local backend).
#
#  Usage:
#    chmod +x start.sh
#    ./start.sh              # first run — installs deps, downloads model, starts all
#    ./start.sh --no-setup   # skip dep install (after first run)
#    ./start.sh --skip-model # skip model download (if already downloaded)
#
#  What it starts:
#    1. Python venv + backend dependencies
#    2. Foundry Local model download + smoke-test (first run only)
#    3. Own MCP server        → http://localhost:8001
#    4. FastAPI backend       → http://localhost:8000
#    5. React frontend        → http://localhost:5173
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[info]${NC}  $*"; }
success() { echo -e "${GREEN}[ok]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $*"; }
error()   { echo -e "${RED}[error]${NC} $*"; exit 1; }
have_command() { command -v "$1" >/dev/null 2>&1; }

pick_python() {
  if have_command python3; then
    echo python3
    return
  fi
  if have_command python; then
    echo python
    return
  fi
  error "Python 3.11+ not found. Install Python and retry."
}

# ── Args ──────────────────────────────────────────────────────────────────────
SKIP_SETUP=false
SKIP_MODEL=false
for arg in "$@"; do
  [[ "$arg" == "--no-setup"    ]] && SKIP_SETUP=true
  [[ "$arg" == "--skip-model"  ]] && SKIP_MODEL=true
done

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/.venv"
PIDS_FILE="$SCRIPT_DIR/.running_pids"
PYTHON_BIN="$(pick_python)"

# ── Cleanup on exit ───────────────────────────────────────────────────────────
cleanup() {
  info "Shutting down…"
  if [[ -f "$PIDS_FILE" ]]; then
    while IFS= read -r pid; do
      kill "$pid" 2>/dev/null || true
    done < "$PIDS_FILE"
    rm -f "$PIDS_FILE"
  fi
}
trap cleanup EXIT INT TERM
> "$PIDS_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Environment file
# ─────────────────────────────────────────────────────────────────────────────
info "Step 1 — Environment configuration"

if [[ ! -f ".env.local" ]]; then
  cp .env.example .env.local
  warn ".env.local created from .env.example"
  warn "Edit .env.local to set your Foundry Local model alias if needed."
  warn "Default: MODEL_BACKEND=foundry_local  FOUNDRY_LOCAL_MODEL_ALIAS=phi-4-mini"
fi

# Load env vars from .env.local (non-export, just for this script)
set -o allexport
# shellcheck disable=SC1091
source .env.local 2>/dev/null || true
set +o allexport

MODEL_ALIAS="${FOUNDRY_LOCAL_MODEL_ALIAS:-phi-4-mini}"
FOUNDRY_LOCAL_ENDPOINT="${FOUNDRY_LOCAL_ENDPOINT:-http://localhost:5273/v1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
OWN_MCP_PORT="${OWN_MCP_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_RELOAD="${BACKEND_RELOAD:-false}"
REQ_FILE="requirements.txt"

wait_for_foundry_local() {
  local health_url="${FOUNDRY_LOCAL_ENDPOINT%/}/models"
  for _ in {1..20}; do
    if curl -fsS "$health_url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_for_http() {
  local url="$1"
  for _ in {1..20}; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

port_in_use() {
  local port="$1"
  lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

if [[ "${MODEL_BACKEND:-foundry_local}" == "azure_foundry" ]]; then
  REQ_FILE="requirements.azure.txt"
fi

success "Environment ready  (backend=$MODEL_BACKEND  model=$MODEL_ALIAS)"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Python virtual environment + dependencies
# ─────────────────────────────────────────────────────────────────────────────
info "Step 2 — Python environment"

if [[ "$SKIP_SETUP" == false ]]; then
  if [[ ! -d "$VENV" ]]; then
    info "Creating virtual environment at .venv …"
    "$PYTHON_BIN" -m venv "$VENV"
  fi

  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  info "Installing Python dependencies from $REQ_FILE …"
  pip install --quiet --upgrade pip
  pip install --quiet -r "$REQ_FILE"
  success "Python dependencies installed"
else
  # shellcheck disable=SC1091
  source "$VENV/bin/activate" 2>/dev/null || {
    error ".venv not found — run without --no-setup first."
  }
  success "Using existing .venv"
fi

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Foundry Local model (local backend only)
# ─────────────────────────────────────────────────────────────────────────────
info "Step 3 — Foundry Local model"

if [[ "${MODEL_BACKEND:-foundry_local}" == "foundry_local" ]]; then
  if [[ "$SKIP_MODEL" == false ]]; then
    info "Downloading/checking model '$MODEL_ALIAS' via Foundry Local SDK …"
    "$PYTHON_BIN" scripts/setup_foundry.py --alias "$MODEL_ALIAS" || {
      error "Model setup failed. Run: $PYTHON_BIN scripts/setup_foundry.py --alias $MODEL_ALIAS"
    }
  else
    warn "--skip-model: assuming model '$MODEL_ALIAS' is already loaded."
  fi

  if wait_for_foundry_local; then
    success "Foundry Local endpoint ready  → $FOUNDRY_LOCAL_ENDPOINT"
  else
    info "Starting Foundry Local web service on $FOUNDRY_LOCAL_ENDPOINT …"
    "$PYTHON_BIN" scripts/setup_foundry.py --alias "$MODEL_ALIAS" --serve --endpoint "$FOUNDRY_LOCAL_ENDPOINT" &
    FOUNDRY_PID=$!
    echo "$FOUNDRY_PID" >> "$PIDS_FILE"

    if wait_for_foundry_local; then
      success "Foundry Local endpoint ready  → $FOUNDRY_LOCAL_ENDPOINT"
    else
      error "Foundry Local is not reachable at $FOUNDRY_LOCAL_ENDPOINT. Start or load '$MODEL_ALIAS' first, or run without --skip-model."
    fi
  fi
else
  info "MODEL_BACKEND=$MODEL_BACKEND — skipping Foundry Local model setup."
  info "Make sure AZURE_AI_PROJECT_ENDPOINT and AZURE_AI_API_KEY are set in .env.local"
fi

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Create local data store directory
# ─────────────────────────────────────────────────────────────────────────────
info "Step 4 — Local storage"
mkdir -p backend/data/store
success "backend/data/store/ ready"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Start own MCP server
# ─────────────────────────────────────────────────────────────────────────────
info "Step 5 — Starting own MCP server on port $OWN_MCP_PORT …"
if port_in_use "$OWN_MCP_PORT"; then
  success "MCP server already listening  → http://localhost:$OWN_MCP_PORT"
else
  "$PYTHON_BIN" -m backend.mcp_server.server &
  MCP_PID=$!
  echo "$MCP_PID" >> "$PIDS_FILE"
  sleep 3
  if kill -0 "$MCP_PID" 2>/dev/null; then
    success "MCP server started (PID $MCP_PID) → http://localhost:$OWN_MCP_PORT"
  else
    warn "MCP server process exited unexpectedly — check output above."
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — Start FastAPI backend
# ─────────────────────────────────────────────────────────────────────────────
info "Step 6 — Starting FastAPI backend on port $BACKEND_PORT …"
UVICORN_ARGS=(
  backend.main:app
  --host 0.0.0.0
  --port "$BACKEND_PORT"
  --log-level info
)

if [[ "$BACKEND_RELOAD" == "true" ]]; then
  UVICORN_ARGS+=(--reload)
fi

if wait_for_http "http://localhost:$BACKEND_PORT/health"; then
  success "Backend API already healthy  → http://localhost:$BACKEND_PORT"
elif port_in_use "$BACKEND_PORT"; then
  error "Port $BACKEND_PORT is already in use but /health did not respond. Clear the process on that port or change BACKEND_PORT."
else
  uvicorn "${UVICORN_ARGS[@]}" &
  API_PID=$!
  echo "$API_PID" >> "$PIDS_FILE"

  if wait_for_http "http://localhost:$BACKEND_PORT/health"; then
    success "Backend API up  → http://localhost:$BACKEND_PORT"
  else
    warn "Backend did not respond in 20s — check logs above."
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — Frontend (npm install + dev server)
# ─────────────────────────────────────────────────────────────────────────────
info "Step 7 — Frontend"

cd frontend

if [[ "$SKIP_SETUP" == false ]]; then
  if ! have_command node; then
    error "Node.js not found. Install Node.js 20+ from https://nodejs.org"
  fi
  info "Installing frontend dependencies …"
  npm install --silent
  success "npm packages installed"
fi

info "Starting React dev server on port $FRONTEND_PORT …"
if wait_for_http "http://localhost:$FRONTEND_PORT/"; then
  success "Frontend already healthy  → http://localhost:$FRONTEND_PORT"
elif port_in_use "$FRONTEND_PORT"; then
  cd ..
  error "Port $FRONTEND_PORT is already in use but the Vite dev server did not respond. Clear the process on that port or change FRONTEND_PORT."
else
  npm run dev -- --port "$FRONTEND_PORT" &
  FRONTEND_PID=$!
  cd ..
  echo "$FRONTEND_PID" >> "$PIDS_FILE"

  if wait_for_http "http://localhost:$FRONTEND_PORT/"; then
    success "Frontend up  → http://localhost:$FRONTEND_PORT"
  else
    warn "Frontend did not respond in 20s — check logs above."
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# All systems go
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  EnterpriseCertIQ is running${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  Dashboard   →  ${BLUE}http://localhost:$FRONTEND_PORT${NC}"
echo -e "  API docs    →  ${BLUE}http://localhost:$BACKEND_PORT/docs${NC}"
echo -e "  API health  →  ${BLUE}http://localhost:$BACKEND_PORT/health${NC}"
echo -e "  MCP server  →  ${BLUE}http://localhost:$OWN_MCP_PORT${NC}"
echo ""
echo -e "  Model backend : ${YELLOW}$MODEL_BACKEND${NC}  ($MODEL_ALIAS)"
echo -e "  Storage       : ${YELLOW}${STORAGE_BACKEND:-local}${NC}  (./backend/data/store/)"
echo ""
echo -e "  Press ${RED}Ctrl+C${NC} to stop all processes."
echo ""

# Block until user interrupts
wait
