#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -x "${PROJECT_ROOT}/venv/Scripts/python.exe" ]]; then
  PYTHON_BIN="${PROJECT_ROOT}/venv/Scripts/python.exe"
elif [[ -x "${PROJECT_ROOT}/venv/bin/python" ]]; then
  PYTHON_BIN="${PROJECT_ROOT}/venv/bin/python"
else
  PYTHON_BIN="python"
fi

DEFAULT_PDF_PATH="src/data/storage/bsr_wp_2025.pdf"

if [[ $# -ge 1 ]]; then
  PDF_PATH="$1"
else
  PDF_PATH="$DEFAULT_PDF_PATH"
fi

if [[ ! -f "$PDF_PATH" ]]; then
  echo "PDF not found: $PDF_PATH"
  echo "Usage: ./scripts/manual_ingest.sh [pdf_path]"
  exit 1
fi

if [[ "${SKIP_MIGRATIONS:-}" != "1" ]]; then
  "$PYTHON_BIN" -m alembic upgrade head
fi
"$PYTHON_BIN" -m src.ai.rag.manual_ingest --pdf-path "$PDF_PATH"
