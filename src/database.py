import json
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from .models import Problem, Submission

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "interview.db"
PROBLEMS_JSON = DATA_DIR / "problems.json"
ADDITIONAL_PROBLEMS_JSON = DATA_DIR / "additional_problems.json"


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS problems (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                difficulty TEXT CHECK(difficulty IN ('easy', 'medium', 'hard')),
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_id TEXT NOT NULL,
                code TEXT NOT NULL,
                language TEXT DEFAULT 'python',
                ai_feedback TEXT,
                passed BOOLEAN,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (problem_id) REFERENCES problems(id)
            );

            CREATE TABLE IF NOT EXISTS review_schedule (
                problem_id TEXT PRIMARY KEY,
                next_review_date DATE NOT NULL,
                interval_days INTEGER DEFAULT 1,
                ease_factor REAL DEFAULT 2.5,
                last_reviewed DATE,
                FOREIGN KEY (problem_id) REFERENCES problems(id)
            );
        """)


def load_problems_from_json(path: Path | None = None) -> int:
    path = path or PROBLEMS_JSON
    with open(path) as f:
        problems = json.load(f)

    count = 0
    with get_connection() as conn:
        for p in problems:
            result = conn.execute(
                "INSERT OR IGNORE INTO problems (id, title, description, difficulty, tags) "
                "VALUES (?, ?, ?, ?, ?)",
                (p["id"], p["title"], p["description"], p["difficulty"], json.dumps(p.get("tags", []))),
            )
            count += result.rowcount

    return count


def load_all_problems() -> int:
    """Load problems from all JSON files (problems.json + additional_problems.json)."""
    count = load_problems_from_json(PROBLEMS_JSON)
    if ADDITIONAL_PROBLEMS_JSON.exists():
        count += load_problems_from_json(ADDITIONAL_PROBLEMS_JSON)
    return count


def _build_filter_clause(
    difficulty: str | None = None, tags: list[str] | None = None
) -> tuple[str, list]:
    """Build WHERE clause and params for difficulty + tag filtering."""
    clauses = []
    params: list = []
    if difficulty:
        clauses.append("difficulty = ?")
        params.append(difficulty)
    if tags:
        for tag in tags:
            clauses.append('tags LIKE ?')
            params.append(f'%"{tag}"%')
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def get_random_problem(
    difficulty: str | None = None, tags: list[str] | None = None
) -> Problem | None:
    where, params = _build_filter_clause(difficulty, tags)
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT * FROM problems{where} ORDER BY RANDOM() LIMIT 1",
            params,
        ).fetchone()
    return Problem.from_row(row) if row else None


def list_problems(
    difficulty: str | None = None, tags: list[str] | None = None
) -> list[Problem]:
    where, params = _build_filter_clause(difficulty, tags)
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM problems{where} ORDER BY difficulty, title",
            params,
        ).fetchall()
    return [Problem.from_row(row) for row in rows]


def get_problem(problem_id: str) -> Problem | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM problems WHERE id = ?", (problem_id,)
        ).fetchone()

    return Problem.from_row(row) if row else None


def save_submission(
    problem_id: str,
    code: str,
    language: str = "python",
    ai_feedback: str | None = None,
    passed: bool | None = None,
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO submissions (problem_id, code, language, ai_feedback, passed) "
            "VALUES (?, ?, ?, ?, ?)",
            (problem_id, code, language, ai_feedback, passed),
        )
        return cursor.lastrowid


def get_submissions(problem_id: str, limit: int = 20) -> list[Submission]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM submissions WHERE problem_id = ? "
            "ORDER BY submitted_at DESC, id DESC LIMIT ?",
            (problem_id, limit),
        ).fetchall()

    return [Submission.from_row(row) for row in rows]


def get_stats() -> dict:
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]

        difficulty_counts = {}
        for row in conn.execute(
            "SELECT difficulty, COUNT(*) as cnt FROM problems GROUP BY difficulty"
        ):
            difficulty_counts[row["difficulty"]] = row["cnt"]

        total_submissions = conn.execute(
            "SELECT COUNT(*) FROM submissions"
        ).fetchone()[0]

        problems_attempted = conn.execute(
            "SELECT COUNT(DISTINCT problem_id) FROM submissions"
        ).fetchone()[0]

    return {
        "total_problems": total,
        "by_difficulty": difficulty_counts,
        "total_submissions": total_submissions,
        "problems_attempted": problems_attempted,
    }


def update_review_schedule(problem_id: str, success: bool) -> dict:
    """Update the review schedule based on performance.

    Returns dict with 'next_review_date' and 'interval_days'.
    """
    today = date.today()

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM review_schedule WHERE problem_id = ?",
            (problem_id,),
        ).fetchone()

        if success:
            if row is None:
                interval_days = 1
            elif row["interval_days"] == 1:
                interval_days = 3
            elif row["interval_days"] == 3:
                interval_days = 7
            else:
                interval_days = row["interval_days"] * 2
        else:
            interval_days = 1

        next_review = today + timedelta(days=interval_days)

        conn.execute(
            "INSERT INTO review_schedule (problem_id, next_review_date, interval_days, last_reviewed) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(problem_id) DO UPDATE SET "
            "next_review_date = excluded.next_review_date, "
            "interval_days = excluded.interval_days, "
            "last_reviewed = excluded.last_reviewed",
            (problem_id, next_review.isoformat(), interval_days, today.isoformat()),
        )

    return {"next_review_date": next_review, "interval_days": interval_days}


def get_due_reviews() -> list[Problem]:
    """Get all problems due for review today or overdue, oldest first."""
    today = date.today().isoformat()

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT p.* FROM problems p "
            "JOIN review_schedule rs ON p.id = rs.problem_id "
            "WHERE rs.next_review_date <= ? "
            "ORDER BY rs.next_review_date ASC",
            (today,),
        ).fetchall()

    return [Problem.from_row(row) for row in rows]


def get_next_review_date(problem_id: str) -> str | None:
    """Get the next scheduled review date for a problem, or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT next_review_date FROM review_schedule WHERE problem_id = ?",
            (problem_id,),
        ).fetchone()

    return row["next_review_date"] if row else None


def get_review_stats() -> dict:
    """Get review-related statistics."""
    today = date.today().isoformat()

    with get_connection() as conn:
        due_today = conn.execute(
            "SELECT COUNT(*) FROM review_schedule WHERE next_review_date <= ?",
            (today,),
        ).fetchone()[0]

        total_reviewed = conn.execute(
            "SELECT COUNT(*) FROM review_schedule WHERE last_reviewed IS NOT NULL"
        ).fetchone()[0]

        # Success rate from submissions that have been reviewed (passed is not null)
        result = conn.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed "
            "FROM submissions WHERE passed IS NOT NULL"
        ).fetchone()
        total_graded = result["total"]
        total_passed = result["passed"] or 0
        avg_success = round(total_passed / total_graded * 100) if total_graded > 0 else 0

        # Current streak: consecutive days with at least one review
        streak = 0
        check_date = date.today()
        while True:
            count = conn.execute(
                "SELECT COUNT(*) FROM review_schedule WHERE last_reviewed = ?",
                (check_date.isoformat(),),
            ).fetchone()[0]
            if count == 0:
                break
            streak += 1
            check_date -= timedelta(days=1)

    return {
        "due_today": due_today,
        "total_reviewed": total_reviewed,
        "avg_success_rate": avg_success,
        "current_streak": streak,
    }


def get_review_info_for_problems(problem_ids: list[str]) -> dict[str, dict]:
    """Get review schedule info for a list of problem IDs.

    Returns {problem_id: {'next_review_date': str, 'interval_days': int, 'last_reviewed': str}}.
    """
    if not problem_ids:
        return {}

    placeholders = ",".join("?" * len(problem_ids))
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM review_schedule WHERE problem_id IN ({placeholders})",
            problem_ids,
        ).fetchall()

    return {
        row["problem_id"]: {
            "next_review_date": row["next_review_date"],
            "interval_days": row["interval_days"],
            "last_reviewed": row["last_reviewed"],
        }
        for row in rows
    }


def get_success_rate(problem_id: str) -> tuple[int, int]:
    """Return (passed_count, total_graded_count) for a problem."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed "
            "FROM submissions WHERE problem_id = ? AND passed IS NOT NULL",
            (problem_id,),
        ).fetchone()

    return (row["passed"] or 0, row["total"])


def get_all_tags() -> dict[str, int]:
    """Return {tag_name: problem_count} for all tags in the database."""
    with get_connection() as conn:
        rows = conn.execute("SELECT tags FROM problems WHERE tags IS NOT NULL").fetchall()

    counts: dict[str, int] = {}
    for row in rows:
        for tag in json.loads(row["tags"]):
            counts[tag] = counts.get(tag, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: (-x[1], x[0])))
