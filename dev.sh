#!/usr/bin/env bash
# Development runner — starts infra (Docker) + backend (uvicorn) + frontend (Next.js).
# Usage:  ./dev.sh [up|down|infra|backend|frontend|migrate|logs|status]
#
# Prerequisites:
#   - Docker + Docker Compose v2
#   - Python venv at backend/.venv  (python -m venv backend/.venv && pip install -r backend/requirements.txt)
#   - Node deps installed           (cd frontend && npm install)
#   - .env.local at repo root       (copy from .env.local.example and fill in values)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_COMPOSE="$ROOT/backend/docker/docker-compose.yml"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
BACKEND_ENVF="$BACKEND_DIR/.env.local"     # used by infra docker-compose + uvicorn settings
FRONTEND_ENVF="$FRONTEND_DIR/.env.local"   # loaded automatically by Next.js
VENV_ACTIVATE="$BACKEND_DIR/.venv/Scripts/activate"   # Windows Git Bash path
# Fallback for Linux/macOS
[[ -f "$VENV_ACTIVATE" ]] || VENV_ACTIVATE="$BACKEND_DIR/.venv/bin/activate"

# ── Helpers ────────────────────────────────────────────────────────────────────

require_env() {
  if [[ ! -f "$BACKEND_ENVF" ]]; then
    echo "ERROR: $BACKEND_ENVF not found."
    echo "       Create backend/.env.local with at least: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB"
    exit 1
  fi
  if [[ ! -f "$FRONTEND_ENVF" ]]; then
    echo "WARNING: $FRONTEND_ENVF not found — Next.js will use defaults / environment variables."
  fi
}

require_venv() {
  if [[ ! -f "$VENV_ACTIVATE" ]]; then
    echo "ERROR: Python venv not found at backend/.venv"
    echo "       Run: python -m venv backend/.venv && pip install -r backend/requirements.txt"
    exit 1
  fi
}

require_node() {
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "ERROR: frontend/node_modules not found."
    echo "       Run: cd frontend && npm install"
    exit 1
  fi
}

# Wrapper — every infra compose call uses the backend env-file and a fixed project name
# (project name determines Docker volume/network names — keep it stable)
dc() {
  docker compose --project-name estimation --env-file "$BACKEND_ENVF" -f "$INFRA_COMPOSE" "$@"
}

# ── Subcommands ────────────────────────────────────────────────────────────────

cmd_infra_up() {
  require_env
  echo "→ Starting dev infrastructure (Postgres :5436, Chroma :8080, Redis :6379)..."
  dc up -d
  dc ps
}

cmd_backend() {
  require_venv
  echo "→ Starting FastAPI backend (uvicorn, hot-reload) on http://localhost:8000 ..."
  # shellcheck source=/dev/null
  source "$VENV_ACTIVATE"
  cd "$BACKEND_DIR"
  uvicorn app.api.server:app --reload --host 0.0.0.0 --port 8000
}

cmd_frontend() {
  require_node
  echo "→ Starting Next.js frontend (dev) on http://localhost:3000 ..."
  cd "$FRONTEND_DIR"
  npm run dev
}

cmd_seed() {
  require_venv
  echo "→ Seeding categories into the database..."
  # shellcheck source=/dev/null
  source "$VENV_ACTIVATE"
  cd "$BACKEND_DIR"
  python scripts/seed_categories.py
}

cmd_ingest() {
  require_venv
  local extra_args=("${@}")
  # shellcheck source=/dev/null
  source "$VENV_ACTIVATE"
  cd "$BACKEND_DIR"
  python scripts/ingest_bsr.py "${extra_args[@]}"
}

cmd_up() {
  require_env
  require_venv
  require_node

  echo "→ Starting dev infrastructure (Postgres :5436, Chroma :8080, Redis :6379)..."
  dc up -d

  # Wait for Postgres to be healthy before seeding / ingesting
  echo "→ Waiting for Postgres to be ready..."
  local attempts=0
  until dc exec -T postgres_db pg_isready -q 2>/dev/null; do
    attempts=$((attempts + 1))
    if [[ $attempts -ge 20 ]]; then
      echo "ERROR: Postgres did not become ready in time."
      exit 1
    fi
    sleep 2
  done
  echo "  Postgres ready."

  # Start backend (no --reload) — startup_event runs Alembic migrations
  echo "→ Starting backend (running migrations)..."
  (
    # shellcheck source=/dev/null
    source "$VENV_ACTIVATE"
    cd "$BACKEND_DIR"
    uvicorn app.api.server:app --host 0.0.0.0 --port 8000
  ) &
  BACKEND_PID=$!

  # Wait for backend to be healthy before seeding / ingesting
  echo "→ Waiting for backend to be ready..."
  local b_attempts=0
  until curl -sf http://localhost:8000/healthz > /dev/null 2>&1; do
    b_attempts=$((b_attempts + 1))
    if [[ $b_attempts -ge 30 ]]; then
      echo "ERROR: Backend did not become ready in time."
      kill $BACKEND_PID 2>/dev/null
      exit 1
    fi
    sleep 2
  done
  echo "  Backend ready."

  # Seed categories (idempotent)
  echo "→ Seeding categories..."
  cmd_seed

  # Ingest BSR data into Postgres + Chroma (skips automatically if already done)
  echo "→ Ingesting BSR data..."
  cmd_ingest

  echo "→ Starting frontend..."

  # Launch frontend in background, capture PID
  (
    cd "$FRONTEND_DIR"
    npm run dev
  ) &
  FRONTEND_PID=$!

  echo ""
  echo "  Backend  → http://localhost:8000   (PID $BACKEND_PID)"
  echo "  Frontend → http://localhost:3000   (PID $FRONTEND_PID)"
  echo ""
  echo "  Press Ctrl+C to stop all services."

  # On Ctrl+C, kill background processes only — Docker infra keeps running.
  # Run ./dev.sh down to explicitly stop the containers.
  trap 'echo ""; echo "→ Stopping backend + frontend (infra stays up — run ./dev.sh down to stop it)..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0' INT TERM

  # Wait for either process to exit (one crash brings everything down)
  wait $BACKEND_PID $FRONTEND_PID
}

case "${1:-up}" in
  up)
    cmd_up
    ;;
  infra)
    cmd_infra_up
    ;;
  backend)
    cmd_backend
    ;;
  frontend)
    cmd_frontend
    ;;
  down)
    echo "→ Stopping dev infrastructure..."
    require_env
    dc down
    ;;
  migrate)
    require_env
    require_venv
    echo "→ Running Alembic migrations..."
    # shellcheck source=/dev/null
    source "$VENV_ACTIVATE"
    cd "$BACKEND_DIR"
    alembic upgrade head
    ;;
  seed)
    require_env
    cmd_seed
    ;;
  ingest)
    require_env
    cmd_ingest "${2:-}"
    ;;
  logs)
    require_env
    dc logs -f --tail=200
    ;;
  status)
    require_env
    dc ps
    ;;
  *)
    echo "Usage: $0 {up|down|infra|backend|frontend|migrate|seed|ingest|logs|status}"
    echo ""
    echo "  up              Start infra + backend + frontend (all-in-one)"
    echo "  infra           Start only Docker infrastructure (Postgres, Chroma, Redis)"
    echo "  backend         Start only the FastAPI backend (uvicorn --reload)"
    echo "  frontend        Start only the Next.js frontend (npm run dev)"
    echo "  down            Stop Docker infrastructure"
    echo "  migrate         Run Alembic database migrations"
    echo "  seed            Seed categories into the database"
    echo "  ingest [pdf]    Ingest BSR PDF into Postgres + ChromaDB (default: bsr_wp_2025.pdf)"
    echo "  logs            Tail Docker infrastructure logs"
    echo "  status          Show Docker infrastructure status"
    echo ""
    echo "  Env files:"
    echo "    backend/.env.local   — Postgres creds, Ollama, SMTP, API keys (required)"
    echo "    frontend/.env.local  — NEXT_PUBLIC_*, AUTH_SECRET (auto-loaded by Next.js)"
    exit 1
    ;;
esac
