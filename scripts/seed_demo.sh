#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

if command -v docker >/dev/null 2>&1 && docker compose ps --status running backend | grep -q backend; then
  docker compose exec backend python manage.py seed_demo
else
  if [[ -x ".venv/bin/python" ]]; then
    VENV_PY=".venv/bin/python"
  elif [[ -x "venv/bin/python" ]]; then
    VENV_PY="venv/bin/python"
  else
    echo "未找到 Python 虚拟环境，请先运行 ./scripts/bootstrap.sh" >&2
    exit 1
  fi
  "$VENV_PY" backend/manage.py seed_demo
fi
