#!/usr/bin/env bash
# One-command production runner for the estimator stack (API-only, frontend on Vercel).
# Usage:  ./run.sh [up|down|logs|rebuild|status]
# Requires: Docker + Docker Compose v2.
# Backend env:  backend/.env
#
# Infrastructure reuse:
#   If dev containers (estimation_postgres / estimation_chroma / estimation_redis)
#   are already running, they are attached to the prod network with service-name
#   aliases and the prod infra services are skipped.
#   Otherwise, prod infrastructure is started via the "infra" profile.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="$ROOT/docker-compose.prod.yml"
BACKEND_ENVF="$ROOT/backend/.env"

# Fixed project name so the network name is always predictable
export COMPOSE_PROJECT_NAME=estimator
PROD_NET="estimator_estimator_net"

# Dev infrastructure container names (from backend/docker/docker-compose.yml)
DEV_POSTGRES="estimation_postgres"
DEV_CHROMA="estimation_chroma"
DEV_REDIS="estimation_redis"

# Validate that a given env file exists and all required keys are non-empty
_check_env_file() {
  local file="$1"; shift
  local label="$1"; shift

  if [[ ! -f "$file" ]]; then
    echo "ERROR: $file not found."
    echo "       Create $label/.env and fill in all values."
    exit 1
  fi

  local missing=()
  for k in "$@"; do
    val=$(grep -E "^${k}=" "$file" 2>/dev/null | head -n1 | cut -d= -f2-)
    [[ -n "$val" ]] || missing+=("$k")
  done

  if (( ${#missing[@]} > 0 )); then
    echo "ERROR: The following required keys are empty in $file:"
    for k in "${missing[@]}"; do echo "  - $k"; done
    exit 1
  fi
}

require_env() {
  _check_env_file "$BACKEND_ENVF" "backend" \
    POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB \
    API_SECRET_KEY \
    OLLAMA_API_KEY OLLAMA_MODEL \
    EMBEDDING_MODEL
}

# Wrapper so every docker compose call uses the backend env file and the prod compose file
dc() {
  docker compose \
    --env-file "$BACKEND_ENVF" \
    -f "$COMPOSE" "$@"
}

# Returns 0 if all three dev infra containers are running
_dev_infra_running() {
  for c in "$DEV_POSTGRES" "$DEV_CHROMA" "$DEV_REDIS"; do
    local state
    state=$(docker inspect --format '{{.State.Running}}' "$c" 2>/dev/null) || return 1
    [[ "$state" == "true" ]] || return 1
  done
}

# Simple ASCII spinner — prints while the given PID is alive
_spinner() {
  local pid=$1 msg=$2
  local i=0
  local frames=('|' '/' '-' '\\')
  while kill -0 "$pid" 2>/dev/null; do
    printf "\r    [%s] %s" "${frames[$i]}" "$msg"
    i=$(( (i+1) % 4 ))
    sleep 0.15
  done
  printf "\r    ✓ %-60s\n" "$msg"
}

# Connect dev containers to the prod network with standard service-name aliases
_connect_dev_infra() {
  echo "→ Dev infrastructure detected — reusing existing containers."

  echo "  [1/4] Creating prod network..."
  docker network create \
    --label "com.docker.compose.network=estimator_net" \
    --label "com.docker.compose.project=estimator" \
    "$PROD_NET" 2>/dev/null || true
  echo "    ✓ Network ready ($PROD_NET)"

  echo "  [2/4] Connecting postgres..."
  docker network connect --alias postgres "$PROD_NET" "$DEV_POSTGRES" 2>/dev/null || true
  echo "    ✓ postgres → $DEV_POSTGRES"

  echo "  [3/4] Connecting chroma..."
  docker network connect --alias chroma "$PROD_NET" "$DEV_CHROMA" 2>/dev/null || true
  echo "    ✓ chroma   → $DEV_CHROMA"

  echo "  [4/4] Connecting redis..."
  docker network connect --alias redis "$PROD_NET" "$DEV_REDIS" 2>/dev/null || true
  echo "    ✓ redis    → $DEV_REDIS"
}

# Disconnect dev containers from the prod network (called on down)
_disconnect_dev_infra() {
  for c in "$DEV_POSTGRES" "$DEV_CHROMA" "$DEV_REDIS"; do
    docker network disconnect "$PROD_NET" "$c" 2>/dev/null || true
  done
}

# Poll backend inside its container until /health responds (max 90 s)
_wait_for_backend() {
  echo "→ Waiting for backend to be ready..."
  local attempts=0
  local frames=('|' '/' '-' '\\')
  local i=0
  until dc exec -T backend curl -sf http://localhost:8000/health > /dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [[ $attempts -ge 30 ]]; then
      printf "\r  ✗ Backend did not become ready after 90 seconds.\n"
      exit 1
    fi
    printf "\r  [%s] Waiting for backend... (%ds elapsed)" "${frames[$i]}" "$((attempts * 3))"
    i=$(( (i+1) % 4 ))
    sleep 3
  done
  printf "\r  ✓ Backend ready (%ds)%-30s\n" "$((attempts * 3))" ""
}

# Seed categories + ingest BSR data (both are idempotent — safe to re-run)
_seed_and_ingest() {
  echo "→ Seeding categories (idempotent)..."
  dc exec -T backend python scripts/seed_categories.py
  echo "→ Ingesting BSR data (skipped automatically if already done)..."
  dc exec -T backend python scripts/ingest_bsr.py
}

# Subcommand dispatch
case "${1:-up}" in
  up)
    require_env
    echo "→ Building images and starting all services..."
    if _dev_infra_running; then
      _connect_dev_infra
      dc up -d --build --no-deps backend caddy
    else
      echo "→ No dev infrastructure found — starting prod infrastructure..."
      dc --profile infra up -d --build
    fi
    _wait_for_backend
    _seed_and_ingest
    dc ps
    ;;
  down)
    echo "→ Stopping all services..."
    _disconnect_dev_infra
    dc --profile infra down
    ;;
  logs)
    dc logs -f --tail=200
    ;;
  rebuild)
    require_env
    echo "→ Rebuilding all images without cache..."
    if _dev_infra_running; then
      _connect_dev_infra
      dc build --no-cache backend caddy
      dc up -d --build --no-deps backend caddy
    else
      dc --profile infra build --no-cache
      dc --profile infra up -d
    fi
    _wait_for_backend
    _seed_and_ingest
    ;;
  status)
    dc ps
    ;;

  seed)
    echo "→ Seeding categories..."
    dc exec -T backend python scripts/seed_categories.py
    ;;
  ingest)
    echo "→ Ingesting BSR data..."
    dc exec -T backend python scripts/ingest_bsr.py ${2:-}
    ;;
  *)
    echo "Usage: $0 {up|down|logs|rebuild|status|seed|ingest}"
    exit 1
    ;;
esac
