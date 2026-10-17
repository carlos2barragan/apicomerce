"""Capa de caché con degradación elegante.

Si hay Redis disponible (variable REDIS_URL y servidor vivo) lo usa.
Si no, cae a una caché en memoria. Esto permite desarrollar y correr
los tests sin necesidad de levantar Redis.

Concepto clave: nunca acoples tu app a una dependencia externa sin un
plan B. Aquí el plan B es la memoria.
"""

import json
import logging
import time
from typing import Any

from app.config import settings

logger = logging.getLogger("app.cache")

# Prefijo de las claves de caché del recurso productos.
# Se centraliza aquí para que cualquier módulo que modifique productos
# (por ejemplo, al crear una orden y descontar stock) pueda invalidarla.
PRODUCTS_CACHE_PREFIX = "products:"

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None  # type: ignore[assignment]


class _MemoryCache:
    """Caché simple en memoria con expiración (TTL)."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at and expires_at < time.time():
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expires_at = time.time() + ttl if ttl else 0.0
        self._store[key] = (expires_at, value)

    def incr(self, key: str, ttl: int) -> int:
        now = time.time()
        item = self._store.get(key)
        if item is None or (item[0] and item[0] < now):
            self._store[key] = (now + ttl, 1)
            return 1
        expires_at, value = item
        self._store[key] = (expires_at, value + 1)
        return value + 1

    def delete_prefix(self, prefix: str) -> None:
        for key in list(self._store):
            if key.startswith(prefix):
                self._store.pop(key, None)


class Cache:
    def __init__(self) -> None:
        self._memory = _MemoryCache()
        self._redis = None
        self._use_redis = False

        if redis is not None and settings.REDIS_URL:
            try:
                client = redis.Redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=1,
                )
                client.ping()
                self._redis = client
                self._use_redis = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis no disponible, uso caché en memoria: %s", exc)

        logger.info("Caché lista (backend=%s)", "redis" if self._use_redis else "memoria")

    def get(self, key: str) -> Any | None:
        if self._use_redis:
            try:
                raw = self._redis.get(key)
                return json.loads(raw) if raw else None
            except Exception:  # noqa: BLE001
                pass
        return self._memory.get(key)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        if self._use_redis:
            try:
                self._redis.set(key, json.dumps(value, default=str), ex=ttl)
                return
            except Exception:  # noqa: BLE001
                pass
        self._memory.set(key, value, ttl)

    def incr(self, key: str, ttl: int) -> int:
        if self._use_redis:
            try:
                value = self._redis.incr(key)
                if value == 1:
                    self._redis.expire(key, ttl)
                return int(value)
            except Exception:  # noqa: BLE001
                pass
        return self._memory.incr(key, ttl)

    def delete_prefix(self, prefix: str) -> None:
        if self._use_redis:
            try:
                for key in self._redis.scan_iter(f"{prefix}*"):
                    self._redis.delete(key)
                return
            except Exception:  # noqa: BLE001
                pass
        self._memory.delete_prefix(prefix)


cache = Cache()
