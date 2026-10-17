from datetime import datetime

from db_service import get_conn


def add_course_doc(user_id: str, course_id: str, title: str, body: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO knowledge_docs (user_id, course_id, title, body, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, course_id, title, body, datetime.utcnow().isoformat()),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_course_docs(user_id: str, course_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, course_id, title, body, created_at
            FROM knowledge_docs
            WHERE user_id = ? AND course_id = ?
            ORDER BY id DESC
            """,
            (user_id, course_id),
        ).fetchall()
    return [dict(r) for r in rows]


def search_course_docs(user_id: str, course_id: str, query: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, body, created_at
            FROM knowledge_docs
            WHERE user_id = ? AND course_id = ? AND (title LIKE ? OR body LIKE ?)
            ORDER BY id DESC
            LIMIT 20
            """,
            (user_id, course_id, f"%{query}%", f"%{query}%"),
        ).fetchall()
    return [dict(r) for r in rows]


def export_markdown_pack(user_id: str, course_id: str) -> str:
    docs = list_course_docs(user_id, course_id)
    lines = [f"# Study Pack: {course_id}", ""]
    for d in docs:
        lines.append(f"## {d['title']}")
        lines.append("")
        lines.append(d["body"])
        lines.append("")
    return "\n".join(lines)


def export_lms_payload(user_id: str, course_id: str) -> dict:
    docs = list_course_docs(user_id, course_id)
    return {
        "course_id": course_id,
        "learner_id": user_id,
        "items": [
            {
                "title": d["title"],
                "content": d["body"],
                "type": "lesson_note",
                "created_at": d["created_at"],
            }
            for d in docs
        ],
    }
