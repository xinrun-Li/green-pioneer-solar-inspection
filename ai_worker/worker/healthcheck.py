import os
import sys

from redis import Redis
from redis.exceptions import RedisError


def main() -> int:
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        Redis.from_url(url, socket_connect_timeout=1).ping()
    except (RedisError, OSError) as exc:
        print(f"AI Worker 尚未连通 Redis: {type(exc).__name__}")
        return 1
    print("AI Worker 原生运行环境与 Redis 连通正常")
    return 0

if __name__ == "__main__":
    sys.exit(main())
