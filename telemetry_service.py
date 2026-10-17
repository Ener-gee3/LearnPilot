from datetime import datetime

from db_service import get_conn


def record_usage(user_id: str, endpoint: str, latency_ms: float, cache_hit: bool, request_tokens: int = 0, response_tokens: int = 0) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO usage_events (user_id, endpoint, cache_hit, request_tokens, response_tokens, latency_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                endpoint,
                1 if cache_hit else 0,
                request_tokens,
                response_tokens,
                latency_ms,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()


def usage_summary(user_id: str) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT endpoint, COUNT(*) AS requests, SUM(cache_hit) AS cache_hits,
                   SUM(request_tokens) AS request_tokens, SUM(response_tokens) AS response_tokens,
                   AVG(latency_ms) AS avg_latency
            FROM usage_events
            WHERE user_id = ?
            GROUP BY endpoint
            ORDER BY requests DESC
            """,
            (user_id,),
        ).fetchall()
    out = []
    for row in rows:
        out.append(
            {
                "endpoint": row["endpoint"],
                "requests": row["requests"] or 0,
                "cache_hits": row["cache_hits"] or 0,
                "request_tokens": row["request_tokens"] or 0,
                "response_tokens": row["response_tokens"] or 0,
                "avg_latency_ms": round(row["avg_latency"] or 0, 2),
            }
        )
    return {"by_endpoint": out}
