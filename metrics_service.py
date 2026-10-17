from collections import defaultdict
from threading import Lock

_lock = Lock()
_request_count = 0
_error_count = 0
_endpoint_counts = defaultdict(int)
_endpoint_latency_total_ms = defaultdict(float)


def record_request(path: str, latency_ms: float, is_error: bool = False) -> None:
    global _request_count, _error_count
    with _lock:
        _request_count += 1
        _endpoint_counts[path] += 1
        _endpoint_latency_total_ms[path] += latency_ms
        if is_error:
            _error_count += 1


def snapshot() -> dict:
    with _lock:
        per_endpoint = {}
        for path, count in _endpoint_counts.items():
            avg = (_endpoint_latency_total_ms[path] / count) if count else 0.0
            per_endpoint[path] = {
                "requests": count,
                "avg_latency_ms": round(avg, 2),
            }
        return {
            "total_requests": _request_count,
            "total_errors": _error_count,
            "error_rate": round((_error_count / _request_count), 4) if _request_count else 0,
            "endpoints": per_endpoint,
        }
