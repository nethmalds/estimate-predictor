#!/usr/bin/env bash
# One-command production runner for the full estimator stack.
# Usage:  ./run.sh [up|down|logs|rebuild|status|migrate]
# Requires: Docker + Docker Compose v2, and a filled-in .env at repo root.
# Dev setup: see .env.local.example — copy to .env.local at repo root (optional)
#            and backend/.env.local.example — copy to backend/.env.local.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="$ROOT/docker-compose.prod.yml"
ENVF="$ROOT/.env"

# Validate that .env exists and all required keys are non-empty
require_env() {
  if [[ ! -f "$ENVF" ]]; then
    echo "ERROR: $ENVF not found."
    echo "       Copy .env.example to .env and fill in all values."
    exit 1
  fi

  local missing=()
  for k in \
    POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB \
    API_SECRET_KEY \
    OLLAMA_API_KEY OLLAMA_MODEL \
    EMBEDDING_MODEL \
    AUTH_SECRET \
    NEXT_PUBLIC_API_BASE_URL; do
    val=$(grep -E "^${k}=" "$ENVF" 2>/dev/null | head -n1 | cut -d= -f2-)
    [[ -n "$val" ]] || missing+=("$k")
  done

  if (( ${#missing[@]} > 0 )); then
    echo "ERROR: The following required keys are empty in $ENVF:"
    for k in "${missing[@]}"; do echo "  - $k"; done
    exit 1
  fi
}

# NEW: Wrapper so every docker compose call uses the prod env-file and compose file
dc() {
  docker compose --env-file "$ENVF" -f "$COMPOSE" "$@"
}

# NEW: Subcommand dispatch
case "${1:-up}" in
  up)
    require_env
    echo "→ Building images and starting all services..."
    dc up -d --build
    dc ps
    ;;
  down)
    echo "→ Stopping all services..."
    dc down
    ;;
  logs)
    dc logs -f --tail=200
    ;;
  rebuild)
    require_env
    echo "→ Rebuilding all images without cache..."
    dc build --no-cache
    dc up -d
    ;;
  status)
    dc ps
    ;;
  migrate)
    echo "→ Running Alembic migrations inside the backend container..."
    dc exec backend alembic upgrade head
    ;;
  *)
    echo "Usage: $0 {up|down|logs|rebuild|status|migrate}"
    exit 1
    ;;
esac
