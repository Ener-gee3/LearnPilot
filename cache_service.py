import time
from threading import Lock

_CACHE: dict[str, tuple[float, object]] = {}
_LOCK = Lock()


def _now() -> float:
    return time.time()


def get_cache(key: str):
    with _LOCK:
        row = _CACHE.get(key)
        if not row:
            return None
        expires_at, value = row
        if expires_at < _now():
            _CACHE.pop(key, None)
            return None
        return value


def set_cache(key: str, value, ttl_seconds: int = 1800):
    with _LOCK:
        _CACHE[key] = (_now() + ttl_seconds, value)
