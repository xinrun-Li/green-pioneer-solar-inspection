#!/usr/bin/env bash
# bootstrap.sh - 初始化绿能先锋开发环境
# 功能：创建虚拟环境、安装依赖、初始化 .env、创建数据目录、执行迁移、创建超级用户、收集静态文件
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ -n "${VENV_DIR:-}" ]]; then
  : "${VENV_DIR}"
elif [[ -x ".venv/bin/python" ]]; then
  VENV_DIR=".venv"
else
  VENV_DIR="venv"
fi
VENV_PY="$VENV_DIR/bin/python"
MANAGE="backend/manage.py"

echo "==> 1/7 检查 .env 配置文件"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "    已从 .env.example 创建 .env，请根据环境修改密钥与数据库配置。"
else
  echo "    .env 已存在，跳过。"
fi

echo "==> 2/7 创建虚拟环境（如不存在）"
if [[ ! -d "$VENV_DIR" ]]; then
  $PYTHON_BIN -m venv "$VENV_DIR"
  echo "    已创建虚拟环境 $VENV_DIR"
else
  echo "    虚拟环境已存在，跳过。"
fi

echo "==> 3/7 安装依赖"
"$VENV_PY" -m pip install --upgrade pip
"$VENV_PY" -m pip install -r backend/requirements/dev.txt

echo "==> 4/7 安装前端依赖"
npm --prefix frontend install

echo "==> 5/7 创建数据目录"
for path in uploads results keyframes reports datasets models temp; do
  mkdir -p "data/$path"
done

echo "==> 6/7 执行数据库迁移"
"$VENV_PY" "$MANAGE" makemigrations
"$VENV_PY" "$MANAGE" migrate

echo "==> 7/7 创建超级用户（如不存在）"
SUPERUSER_EMAIL="${DJANGO_SUPERUSER_EMAIL:-admin@example.com}"
SUPERUSER_USERNAME="${DJANGO_SUPERUSER_USERNAME:-admin}"
SUPERUSER_PASSWORD="${DJANGO_SUPERUSER_PASSWORD:-admin123456}"
if "$VENV_PY" "$MANAGE" shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); exit(0 if U.objects.filter(username='${SUPERUSER_USERNAME}').exists() else 1)" 2>/dev/null; then
  echo "    超级用户 ${SUPERUSER_USERNAME} 已存在，跳过。"
else
  DJANGO_SUPERUSER_USERNAME="$SUPERUSER_USERNAME" \
  DJANGO_SUPERUSER_EMAIL="$SUPERUSER_EMAIL" \
  DJANGO_SUPERUSER_PASSWORD="$SUPERUSER_PASSWORD" \
  "$VENV_PY" "$MANAGE" createsuperuser --noinput || {
    echo "    自动创建失败，请手动执行：$VENV_PY $MANAGE createsuperuser"
  }
fi

echo "==> 收集静态文件"
"$VENV_PY" "$MANAGE" collectstatic --noinput

echo ""
echo "✅ 初始化完成！"
echo "   - 启动后端：./scripts/start.sh"
echo "   - 启动 Docker：./scripts/start.sh --docker"
echo "   - 查看健康状态：./scripts/healthcheck.sh"
