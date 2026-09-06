#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

PYTHON=".venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="venv/bin/python"
fi
if [[ ! -x "$PYTHON" ]]; then
  echo "未找到 Python 虚拟环境，请先运行 ./scripts/bootstrap.sh" >&2
  exit 1
fi

"$PYTHON" backend/manage.py migrate --noinput
"$PYTHON" backend/manage.py flush --noinput
"$PYTHON" backend/manage.py seed_demo
echo "演示数据已重置。请按需重新创建 Django 管理员账户。"
