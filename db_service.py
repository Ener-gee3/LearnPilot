import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.getenv("LEARNPILOT_DB_PATH", "learnpilot.db"))


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                mode TEXT NOT NULL,
                topic TEXT NOT NULL,
                response_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learner_profiles (
                user_id TEXT PRIMARY KEY,
                persona TEXT NOT NULL DEFAULT 'beginner',
                target_exam_date TEXT,
                daily_minutes INTEGER NOT NULL DEFAULT 30,
                preferred_mode TEXT,
                primary_goal TEXT NOT NULL DEFAULT 'better learning outcomes',
                weak_topics_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learner_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                score REAL NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS review_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                card_front TEXT NOT NULL,
                card_back TEXT NOT NULL,
                interval_days INTEGER NOT NULL,
                due_at TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                cache_hit INTEGER NOT NULL DEFAULT 0,
                request_tokens INTEGER NOT NULL DEFAULT 0,
                response_tokens INTEGER NOT NULL DEFAULT 0,
                latency_ms REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                course_id TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def migrate_history_json_if_needed(history_file: str = "history.json", user_id: str = "legacy") -> int:
    if not Path(history_file).exists():
        return 0
    with open(history_file, "r", encoding="utf-8") as f:
        try:
            items = json.load(f)
        except Exception:
            return 0

    moved = 0
    with get_conn() as conn:
        for item in items:
            conn.execute(
                """
                INSERT INTO learning_history (user_id, timestamp, mode, topic, response_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    item.get("timestamp", ""),
                    item.get("mode", ""),
                    item.get("topic", ""),
                    json.dumps(item.get("response", {})),
                ),
            )
            moved += 1
        conn.commit()

    backup = Path(history_file + ".migrated")
    Path(history_file).rename(backup)
    return moved
