#!/usr/bin/env bash
# stop.sh - 停止绿能先锋服务
# 用法：
#   ./scripts/stop.sh            停止本地 Django + 前端
#   ./scripts/stop.sh --docker   停止 Docker Compose（含本地进程）
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

STOP_DOCKER=false
for arg in "$@"; do
  case "$arg" in
    --docker) STOP_DOCKER=true ;;
    -h|--help)
      echo "用法: ./scripts/stop.sh [--docker]"
      echo "  --docker  同时停止 Docker Compose 服务"
      exit 0
      ;;
  esac
done

echo "==> 停止 Celery Worker"
if [[ -f .tmp/celery.pid ]]; then
  CELERY_PID="$(cat .tmp/celery.pid)"
  if kill -0 "$CELERY_PID" 2>/dev/null; then
    kill "$CELERY_PID"
    echo "    已停止 Celery Worker (PID $CELERY_PID)"
  fi
  rm -f .tmp/celery.pid
else
  if pgrep -f "celery.*worker" >/dev/null 2>&1; then
    pkill -f "celery.*worker" || true
    echo "    已停止 Celery Worker 进程。"
  fi
fi

echo "==> 停止 Django 后端"
if [[ -f .tmp/backend.pid ]]; then
  BACKEND_PID="$(cat .tmp/backend.pid)"
  if kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID"
    echo "    已停止后端 (PID $BACKEND_PID)"
  else
    echo "    后端进程已不在运行。"
  fi
  rm -f .tmp/backend.pid
else
  # 兼容旧版：按进程名停止
  if pgrep -f "manage.py runserver" >/dev/null 2>&1; then
    pkill -f "manage.py runserver" || true
    echo "    已停止 runserver 进程。"
  else
    echo "    未发现运行中的 runserver 进程。"
  fi
fi

echo "==> 停止前端"
if [[ -f .tmp/frontend.pid ]]; then
  FRONTEND_PID="$(cat .tmp/frontend.pid)"
  if kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID"
    echo "    已停止前端 (PID $FRONTEND_PID)"
  fi
  rm -f .tmp/frontend.pid
else
  if pgrep -f "vite" >/dev/null 2>&1; then
    pkill -f "vite" || true
    echo "    已停止 vite 进程。"
  fi
fi

if [[ "$STOP_DOCKER" == "true" ]]; then
  echo "==> 停止 Docker Compose"
  if command -v docker >/dev/null 2>&1; then
    docker compose down
  else
    echo "    Docker 未安装，跳过。"
  fi
fi

echo "✅ 绿能先锋服务已停止。"
