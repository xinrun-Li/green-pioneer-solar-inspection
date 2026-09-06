.PHONY: bootstrap start stop health test migrate migrations shell \
        superuser logs clean reset-demo seed-demo lint format \
        celery celery-stop register-yolo

# Prefer the modern local environment when present; bootstrap installations may
# still use venv/ for clean machines.
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,venv/bin/python)
DJANGO=cd backend && ../$(PYTHON)

# ---- 环境初始化 ----
bootstrap:
	./scripts/bootstrap.sh

# ---- 启动 / 停止 ----
start:
	./scripts/start.sh

start-celery:
	./scripts/start.sh --celery

stop:
	./scripts/stop.sh

# ---- 健康检查 ----
health:
	./scripts/healthcheck.sh

# ---- 数据库迁移 ----
migrations:
	$(DJANGO) manage.py makemigrations

migrate:
	$(DJANGO) manage.py migrate

# ---- 管理工具 ----
shell:
	$(DJANGO) manage.py shell

superuser:
	$(DJANGO) manage.py createsuperuser

# ---- Celery ----
celery:
	$(DJANGO) -m celery -A config worker --loglevel=info

celery-status:
	$(DJANGO) -m celery -A config inspect ping

# ---- 日志 ----
logs:
	tail -f .tmp/backend.log

logs-celery:
	tail -f .tmp/celery.log

# ---- 清理 ----
clean:
	rm -rf .tmp
	rm -rf backend/.coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete

# ---- 测试 ----
test:
	cd backend && ../$(PYTHON) manage.py test apps.accounts apps.uploads apps.recognition apps.datasets apps.training apps.events apps.inspections apps.assistant apps.reports
	cd frontend && npm run type-check

# ---- 演示数据 ----
reset-demo:
	./scripts/reset_demo.sh

seed-demo:
	./scripts/seed_demo.sh

register-yolo:
	$(DJANGO) manage.py register_yolo_model --activate

# ---- 代码质量 ----
lint:
	cd backend && ../$(PYTHON) -m ruff check

format:
	cd backend && ../$(PYTHON) -m ruff format
