import json
from datetime import datetime, timedelta

from db_service import get_conn


DEFAULT_PREREQS = {
    "dynamic programming": ["recursion", "arrays", "time complexity"],
    "neural networks": ["linear algebra", "probability", "gradient descent"],
    "operating systems": ["process", "memory", "threads"],
}


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def get_or_create_profile(user_id: str) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM learner_profiles WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            return dict(row)

        now = _now_iso()
        conn.execute(
            """
            INSERT INTO learner_profiles (
                user_id, persona, target_exam_date, daily_minutes, preferred_mode,
                primary_goal, weak_topics_json, created_at, updated_at
            ) VALUES (?, 'beginner', NULL, 30, NULL, 'better learning outcomes', '[]', ?, ?)
            """,
            (user_id, now, now),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM learner_profiles WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row)


def update_profile(user_id: str, payload: dict) -> dict:
    profile = get_or_create_profile(user_id)
    weak_topics = payload.get("weak_topics")
    if weak_topics is not None:
        weak_topics_json = json.dumps(weak_topics)
    else:
        weak_topics_json = profile.get("weak_topics_json", "[]")

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE learner_profiles
            SET persona = ?,
                target_exam_date = ?,
                daily_minutes = ?,
                preferred_mode = ?,
                primary_goal = ?,
                weak_topics_json = ?,
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                payload.get("persona", profile["persona"]),
                payload.get("target_exam_date", profile["target_exam_date"]),
                payload.get("daily_minutes", profile["daily_minutes"]),
                payload.get("preferred_mode", profile["preferred_mode"]),
                payload.get("primary_goal", profile["primary_goal"]),
                weak_topics_json,
                _now_iso(),
                user_id,
            ),
        )
        conn.commit()

    latest = get_or_create_profile(user_id)
    latest["weak_topics"] = json.loads(latest.pop("weak_topics_json", "[]"))
    return latest


def record_progress(user_id: str, topic: str, score: float, source: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO learner_progress (user_id, topic, score, source, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, topic, score, source, _now_iso()),
        )
        conn.commit()


def progress_summary(user_id: str) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT topic,
                   ROUND(AVG(score), 2) as avg_score,
                   COUNT(*) as attempts
            FROM learner_progress
            WHERE user_id = ?
            GROUP BY topic
            ORDER BY avg_score ASC, attempts DESC
            """,
            (user_id,),
        ).fetchall()

    by_topic = [dict(r) for r in rows]
    weak = [r["topic"] for r in by_topic if (r["avg_score"] or 0) < 0.65][:5]
    strong = [r["topic"] for r in by_topic if (r["avg_score"] or 0) >= 0.8][:5]
    return {"topics": by_topic, "weak_topics": weak, "strong_topics": strong}


def recommend_next_topic(user_id: str, topic: str) -> dict:
    summary = progress_summary(user_id)
    profile = get_or_create_profile(user_id)

    avg = None
    for row in summary["topics"]:
        if row["topic"].lower() == topic.lower():
            avg = row["avg_score"]
            break

    if avg is None:
        difficulty = "beginner"
    elif avg < 0.55:
        difficulty = "bridge"
    elif avg < 0.8:
        difficulty = "intermediate"
    else:
        difficulty = "advanced"

    weak_topics = json.loads(profile.get("weak_topics_json", "[]"))
    recommendation = weak_topics[0] if weak_topics else (summary["weak_topics"][0] if summary["weak_topics"] else topic)

    return {
        "topic": topic,
        "recommended_difficulty": difficulty,
        "recommended_next_topic": recommendation,
        "persona": profile.get("persona", "beginner"),
    }


def detect_prerequisites(topic: str) -> list[str]:
    lower = topic.lower()
    for key, prereqs in DEFAULT_PREREQS.items():
        if key in lower:
            return prereqs
    return ["core concepts", "key definitions"]


def bridge_lesson(topic: str) -> dict:
    prereqs = detect_prerequisites(topic)
    bridge_steps = [f"Review prerequisite: {p}" for p in prereqs]
    bridge_steps.append(f"Practice a short foundational problem related to {topic}")
    return {"topic": topic, "prerequisites": prereqs, "bridge_steps": bridge_steps}


def schedule_flashcards(user_id: str, topic: str, cards: list[dict]) -> list[dict]:
    now = datetime.utcnow()
    out = []
    with get_conn() as conn:
        for card in cards:
            diff = (card.get("difficulty") or "medium").lower()
            interval = 1 if diff == "hard" else (2 if diff == "medium" else 4)
            due_at = (now + timedelta(days=interval)).isoformat()
            conn.execute(
                """
                INSERT INTO review_schedule (
                    user_id, topic, card_front, card_back, interval_days, due_at, difficulty,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    topic,
                    card.get("front", ""),
                    card.get("back", ""),
                    interval,
                    due_at,
                    diff,
                    _now_iso(),
                    _now_iso(),
                ),
            )
            out.append({"front": card.get("front", ""), "due_at": due_at, "interval_days": interval})
        conn.commit()
    return out


def due_reviews(user_id: str) -> list[dict]:
    now = _now_iso()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, topic, card_front, card_back, due_at, interval_days, difficulty
            FROM review_schedule
            WHERE user_id = ? AND due_at <= ?
            ORDER BY due_at ASC
            LIMIT 100
            """,
            (user_id, now),
        ).fetchall()
    return [dict(r) for r in rows]


def build_goal_plan(user_id: str) -> dict:
    profile = get_or_create_profile(user_id)
    weak_topics = json.loads(profile.get("weak_topics_json", "[]"))
    summary = progress_summary(user_id)
    weak_auto = summary["weak_topics"][:3]
    all_weak = list(dict.fromkeys(weak_topics + weak_auto))
    daily = int(profile.get("daily_minutes", 30) or 30)
    focus_blocks = max(1, daily // 15)

    plan = [
        {"block": i + 1, "minutes": 15, "focus": all_weak[i % len(all_weak)] if all_weak else "current topic reinforcement"}
        for i in range(focus_blocks)
    ]

    return {
        "target_exam_date": profile.get("target_exam_date"),
        "daily_minutes": daily,
        "focus_blocks": plan,
    }
