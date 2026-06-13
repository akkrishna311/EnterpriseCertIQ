#!/usr/bin/env bash
#
# laptop-setup.sh — bring up EnterpriseCertIQ on a fresh machine (Azure path).
#
# Run from the repo root after:  git clone <repo> && cd enterprisecertiq && git checkout develop
#
# It will: create the venv, install backend + Azure deps, install frontend deps,
# and make sure .env.local exists (copied from .env.example for you to fill in).
# It does NOT start servers and does NOT touch any secrets you haven't entered.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo "▶ EnterpriseCertIQ setup in: $ROOT"

# 1. Python venv + deps -------------------------------------------------------
if [ ! -d .venv ]; then
  echo "▶ Creating Python venv (.venv)…"
  python3 -m venv .venv
fi
echo "▶ Installing backend + Azure dependencies…"
.venv/bin/pip install --upgrade pip >/dev/null
.venv/bin/pip install -r requirements.txt
[ -f requirements.azure.txt ] && .venv/bin/pip install -r requirements.azure.txt

# 2. Frontend deps ------------------------------------------------------------
echo "▶ Installing frontend dependencies…"
npm install --prefix frontend

# 3. .env.local (NEVER committed — gitignored) --------------------------------
if [ ! -f .env.local ]; then
  cp .env.example .env.local
  echo "⚠  Created .env.local from .env.example."
  echo "   EDIT IT NOW and fill in your Azure values, then keep:"
  echo "     MODEL_BACKEND=azure_foundry"
  echo "     ENABLE_TELEMETRY=true"
  echo "     AZURE_AI_API_KEY=...    AZURE_SEARCH_KEY=..."
  echo "     APPLICATIONINSIGHTS_CONNECTION_STRING=..."
  echo "   NEVER commit .env.local."
else
  echo "✓ .env.local already present (left untouched)."
fi

# 4. Notes --------------------------------------------------------------------
cat <<'EOF'

✓ Setup complete.

backend/data/store/ is gitignored, so this machine starts with an empty store.
Re-run "Build My Plan" a couple of times to regenerate demo data (plans, traces),
or copy backend/data/store/ over from the other laptop for the exact same demo state.

To run the stack:
  Backend:   .venv/bin/uvicorn backend.main:app --reload --port 8000
  Frontend:  npm run dev --prefix frontend        # http://localhost:5173

EOF
