from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.utils.timezone import now
from redis import Redis
from redis.exceptions import RedisError


def health(request):
    services = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        services["database"] = {"status": "ok"}
    except DatabaseError as exc:
        services["database"] = {"status": "unavailable", "detail": type(exc).__name__}

    try:
        Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=0.5).ping()
        services["redis"] = {"status": "ok"}
    except (RedisError, OSError):
        services["redis"] = {"status": "unavailable"}

    services["worker"] = {"status": "not_configured", "detail": "原生 AI Worker 将在阶段 2 接入"}
    services["mock_inference"] = {"status": "ok", "detail": "手动模拟执行入口可用"}
    overall = "ok" if services["database"]["status"] == services["redis"]["status"] == "ok" else "degraded"
    return JsonResponse({
        "status": overall, "service": "green-pioneer-api", "version": "0.1.0",
        "timestamp": now().isoformat(), "services": services,
    }, status=200)
