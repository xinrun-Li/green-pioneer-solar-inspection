#!/usr/bin/env bash
# start.sh - 启动绿能先锋服务
# 用法：
#   ./scripts/start.sh           启动 Django 开发服务器 + 前端
#   ./scripts/start.sh --docker  启动 Docker Compose + 前端
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ -x ".venv/bin/python" ]]; then
  VENV_PY=".venv/bin/python"
else
  VENV_PY="venv/bin/python"
fi
MANAGE="backend/manage.py"
MODE="local"
START_CELERY=false

for arg in "$@"; do
  case "$arg" in
    --docker) MODE="docker" ;;
    --local) MODE="local" ;;
    --celery) START_CELERY=true ;;
    -h|--help)
      echo "用法: ./scripts/start.sh [--docker|--local] [--celery]"
      echo "  --docker  启动 Docker Compose（后端+数据库）"
      echo "  --local   启动本地 Django 开发服务器（默认）"
      echo "  --celery  同时启动 Celery Worker"
      exit 0
      ;;
  esac
done

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已创建 .env，请按需修改配置。"
fi

# 加载 .env 环境变量（供本地模式使用，跳过注释与空行）
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1090
  source <(grep -vE '^\s*(#|$)' .env)
  set +a
fi

if [[ "$MODE" == "docker" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "❌ 未检测到 Docker。请先安装并启动 Docker Desktop，然后重新执行。" >&2
    exit 1
  fi
  echo "==> 启动 Docker Compose"
  docker compose up -d --build
else
  echo "==> 启动 Django 开发服务器 (0.0.0.0:8000)"
  mkdir -p .tmp
  if [[ -f .tmp/backend.pid ]] && kill -0 "$(cat .tmp/backend.pid)" 2>/dev/null; then
    echo "后端已在运行 (PID $(cat .tmp/backend.pid))。"
  else
    "$VENV_PY" "$MANAGE" runserver 0.0.0.0:8000 > .tmp/backend.log 2>&1 &
    echo $! > .tmp/backend.pid
    echo "后端已启动，日志：.tmp/backend.log"
  fi
fi

# 启动 Celery Worker（本地 + docker 模式均支持，需配置 REDIS_URL）
if [[ "$START_CELERY" == "true" ]] && [[ -n "${REDIS_URL:-}" ]]; then
  echo "==> 启动 Celery Worker"
  if [[ -f .tmp/celery.pid ]] && kill -0 "$(cat .tmp/celery.pid)" 2>/dev/null; then
    echo "Celery Worker 已在运行 (PID $(cat .tmp/celery.pid))。"
  else
    (cd backend && "../$VENV_PY" -m celery -A config worker --loglevel=info) > .tmp/celery.log 2>&1 &
    echo $! > .tmp/celery.pid
    echo "Celery Worker 已启动，日志：.tmp/celery.log"
  fi
elif [[ "$START_CELERY" == "true" ]]; then
  echo "⚠️ 未配置 REDIS_URL，跳过 Celery Worker 启动。"
fi

if [[ -f .tmp/frontend.pid ]] && kill -0 "$(cat .tmp/frontend.pid)" 2>/dev/null; then
  echo "前端已在运行。"
else
  mkdir -p .tmp
  npm --prefix frontend run dev > .tmp/frontend.log 2>&1 &
  echo $! > .tmp/frontend.pid
fi

echo ""
echo "绿能先锋已启动："
echo "  - 前端:   http://localhost:5173"
echo "  - 后端:   http://localhost:8000"
echo "  - 健康:   http://localhost:8000/api/v1/health"
