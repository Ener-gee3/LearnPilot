from collections import defaultdict, deque
from datetime import datetime, timedelta
from threading import Lock

RATE_PER_MINUTE = 90
DAILY_QUOTA = 2000

_minute_windows: dict[str, deque] = defaultdict(deque)
_daily_counts: dict[str, tuple[str, int]] = {}
_lock = Lock()


class RateLimitError(Exception):
    pass


def check_rate_limit(user_id: str) -> None:
    now = datetime.utcnow()
    minute_ago = now - timedelta(minutes=1)
    day_key = now.strftime("%Y-%m-%d")

    with _lock:
        q = _minute_windows[user_id]
        while q and q[0] < minute_ago:
            q.popleft()
        if len(q) >= RATE_PER_MINUTE:
            raise RateLimitError("Per-minute rate limit exceeded")
        q.append(now)

        key, count = _daily_counts.get(user_id, (day_key, 0))
        if key != day_key:
            key, count = day_key, 0
        count += 1
        if count > DAILY_QUOTA:
            raise RateLimitError("Daily quota exceeded")
        _daily_counts[user_id] = (key, count)
