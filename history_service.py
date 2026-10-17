import json
from datetime import datetime
from typing import Any

from db_service import get_conn, init_db, migrate_history_json_if_needed


init_db()
try:
    migrate_history_json_if_needed()
except Exception:
    pass


class HistoryService:
    @staticmethod
    def save_session(mode: str, topic: str, response: dict[str, Any], user_id: str = "anonymous") -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO learning_history (user_id, timestamp, mode, topic, response_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, datetime.utcnow().isoformat(), mode, topic, json.dumps(response)),
            )
            conn.commit()

    @staticmethod
    def get_history(user_id: str = "anonymous", limit: int = 100) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT timestamp, mode, topic, response_json
                FROM learning_history
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        out = []
        for row in rows:
            try:
                response = json.loads(row["response_json"])
            except Exception:
                response = {}
            out.append(
                {
                    "timestamp": row["timestamp"],
                    "mode": row["mode"],
                    "topic": row["topic"],
                    "response": response,
                }
            )
        return out
