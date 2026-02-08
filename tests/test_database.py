import json
import tempfile
from pathlib import Path

import pytest

from src import database
from src.models import Problem, Submission


@pytest.fixture(autouse=True)
def tmp_database(tmp_path, monkeypatch):
    """Redirect database and problems.json to a temp directory for each test."""
    db_path = tmp_path / "interview.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)

    # Create a small test problems file
    problems = [
        {
            "id": "test-easy",
            "title": "Test Easy",
            "description": "An easy test problem.",
            "difficulty": "easy",
            "tags": ["arrays"],
        },
        {
            "id": "test-medium",
            "title": "Test Medium",
            "description": "A medium test problem.",
            "difficulty": "medium",
            "tags": ["strings", "hash-table"],
        },
        {
            "id": "test-hard",
            "title": "Test Hard",
            "description": "A hard test problem.",
            "difficulty": "hard",
            "tags": ["graphs", "dfs"],
        },
    ]
    problems_file = tmp_path / "problems.json"
    problems_file.write_text(json.dumps(problems))
    monkeypatch.setattr(database, "PROBLEMS_JSON", problems_file)

    return tmp_path


class TestInitDb:
    def test_creates_tables(self):
        database.init_db()

        with database.get_connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {row["name"] for row in tables}

        assert "problems" in table_names
        assert "submissions" in table_names
        assert "review_schedule" in table_names

    def test_idempotent(self):
        database.init_db()
        database.init_db()  # Should not raise


class TestLoadProblems:
    def test_loads_problems(self):
        database.init_db()
        count = database.load_problems_from_json()
        assert count == 3

    def test_idempotent_load(self):
        database.init_db()
        first = database.load_problems_from_json()
        second = database.load_problems_from_json()
        assert first == 3
        assert second == 0  # INSERT OR IGNORE — no new rows


class TestGetRandomProblem:
    def test_returns_a_problem(self):
        database.init_db()
        database.load_problems_from_json()

        problem = database.get_random_problem()
        assert problem is not None
        assert isinstance(problem, Problem)

    def test_filters_by_difficulty(self):
        database.init_db()
        database.load_problems_from_json()

        problem = database.get_random_problem(difficulty="easy")
        assert problem is not None
        assert problem.difficulty == "easy"
        assert problem.id == "test-easy"

    def test_returns_none_for_empty_db(self):
        database.init_db()
        assert database.get_random_problem() is None


class TestListProblems:
    def test_returns_all(self):
        database.init_db()
        database.load_problems_from_json()

        problems = database.list_problems()
        assert len(problems) == 3

    def test_filters_by_difficulty(self):
        database.init_db()
        database.load_problems_from_json()

        problems = database.list_problems(difficulty="medium")
        assert len(problems) == 1
        assert problems[0].id == "test-medium"


class TestGetProblem:
    def test_found(self):
        database.init_db()
        database.load_problems_from_json()

        problem = database.get_problem("test-easy")
        assert problem is not None
        assert problem.title == "Test Easy"
        assert problem.tags == ["arrays"]

    def test_not_found(self):
        database.init_db()
        assert database.get_problem("nonexistent") is None


class TestSubmissions:
    def test_save_and_retrieve(self):
        database.init_db()
        database.load_problems_from_json()

        sub_id = database.save_submission(
            problem_id="test-easy",
            code="def solve(): pass",
            language="python",
            ai_feedback="Good start!",
            passed=True,
        )
        assert sub_id is not None

        subs = database.get_submissions("test-easy")
        assert len(subs) == 1
        assert isinstance(subs[0], Submission)
        assert subs[0].problem_id == "test-easy"
        assert subs[0].code == "def solve(): pass"
        assert subs[0].ai_feedback == "Good start!"
        assert subs[0].passed is True

    def test_ordering_newest_first(self):
        database.init_db()
        database.load_problems_from_json()

        database.save_submission("test-easy", "first", "python", "fb1", True)
        database.save_submission("test-easy", "second", "python", "fb2", False)

        subs = database.get_submissions("test-easy")
        assert len(subs) == 2
        assert subs[0].code == "second"  # newest first
        assert subs[1].code == "first"

    def test_empty_submissions(self):
        database.init_db()
        database.load_problems_from_json()

        subs = database.get_submissions("test-easy")
        assert subs == []


class TestGetStats:
    def test_stats_shape(self):
        database.init_db()
        database.load_problems_from_json()

        stats = database.get_stats()
        assert stats["total_problems"] == 3
        assert stats["by_difficulty"]["easy"] == 1
        assert stats["by_difficulty"]["medium"] == 1
        assert stats["by_difficulty"]["hard"] == 1
        assert stats["total_submissions"] == 0
        assert stats["problems_attempted"] == 0
