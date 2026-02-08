import json
from datetime import date, timedelta

import pytest

from src import database


@pytest.fixture(autouse=True)
def tmp_database(tmp_path, monkeypatch):
    """Redirect database and problems.json to a temp directory for each test."""
    db_path = tmp_path / "interview.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)

    problems = [
        {
            "id": "two-sum",
            "title": "Two Sum",
            "description": "Find two numbers that add up to target.",
            "difficulty": "easy",
            "tags": ["arrays"],
        },
        {
            "id": "valid-parens",
            "title": "Valid Parentheses",
            "description": "Check if parentheses are balanced.",
            "difficulty": "easy",
            "tags": ["stacks"],
        },
        {
            "id": "longest-substring",
            "title": "Longest Substring",
            "description": "Find longest substring without repeating chars.",
            "difficulty": "medium",
            "tags": ["strings"],
        },
    ]
    problems_file = tmp_path / "problems.json"
    problems_file.write_text(json.dumps(problems))
    monkeypatch.setattr(database, "PROBLEMS_JSON", problems_file)

    database.init_db()
    database.load_problems_from_json()
    return tmp_path


class TestUpdateReviewSchedule:
    def test_first_success_sets_interval_1(self):
        result = database.update_review_schedule("two-sum", success=True)
        assert result["interval_days"] == 1
        assert result["next_review_date"] == date.today() + timedelta(days=1)

    def test_second_success_sets_interval_3(self):
        database.update_review_schedule("two-sum", success=True)  # interval=1
        result = database.update_review_schedule("two-sum", success=True)  # interval=3
        assert result["interval_days"] == 3

    def test_third_success_sets_interval_7(self):
        database.update_review_schedule("two-sum", success=True)  # 1
        database.update_review_schedule("two-sum", success=True)  # 3
        result = database.update_review_schedule("two-sum", success=True)  # 7
        assert result["interval_days"] == 7

    def test_fourth_success_doubles(self):
        database.update_review_schedule("two-sum", success=True)  # 1
        database.update_review_schedule("two-sum", success=True)  # 3
        database.update_review_schedule("two-sum", success=True)  # 7
        result = database.update_review_schedule("two-sum", success=True)  # 14
        assert result["interval_days"] == 14

    def test_struggle_resets_to_1(self):
        database.update_review_schedule("two-sum", success=True)  # 1
        database.update_review_schedule("two-sum", success=True)  # 3
        result = database.update_review_schedule("two-sum", success=False)  # reset
        assert result["interval_days"] == 1
        assert result["next_review_date"] == date.today() + timedelta(days=1)

    def test_struggle_then_success_restarts_progression(self):
        database.update_review_schedule("two-sum", success=True)   # 1
        database.update_review_schedule("two-sum", success=True)   # 3
        database.update_review_schedule("two-sum", success=False)  # reset to 1
        result = database.update_review_schedule("two-sum", success=True)  # 1 -> 3
        assert result["interval_days"] == 3

    def test_first_struggle_sets_interval_1(self):
        result = database.update_review_schedule("two-sum", success=False)
        assert result["interval_days"] == 1


class TestGetDueReviews:
    def test_no_reviews_returns_empty(self):
        assert database.get_due_reviews() == []

    def test_due_today_is_returned(self):
        # Schedule for tomorrow, then override to today
        database.update_review_schedule("two-sum", success=True)
        today = date.today().isoformat()
        with database.get_connection() as conn:
            conn.execute(
                "UPDATE review_schedule SET next_review_date = ? WHERE problem_id = ?",
                (today, "two-sum"),
            )

        due = database.get_due_reviews()
        assert len(due) == 1
        assert due[0].id == "two-sum"

    def test_overdue_is_returned(self):
        database.update_review_schedule("two-sum", success=True)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        with database.get_connection() as conn:
            conn.execute(
                "UPDATE review_schedule SET next_review_date = ? WHERE problem_id = ?",
                (yesterday, "two-sum"),
            )

        due = database.get_due_reviews()
        assert len(due) == 1

    def test_future_not_returned(self):
        database.update_review_schedule("two-sum", success=True)
        # Default schedule is tomorrow, so it shouldn't be due
        due = database.get_due_reviews()
        assert len(due) == 0

    def test_sorted_oldest_first(self):
        database.update_review_schedule("two-sum", success=True)
        database.update_review_schedule("valid-parens", success=True)

        today = date.today()
        yesterday = (today - timedelta(days=1)).isoformat()
        with database.get_connection() as conn:
            conn.execute(
                "UPDATE review_schedule SET next_review_date = ? WHERE problem_id = ?",
                (yesterday, "two-sum"),
            )
            conn.execute(
                "UPDATE review_schedule SET next_review_date = ? WHERE problem_id = ?",
                (today.isoformat(), "valid-parens"),
            )

        due = database.get_due_reviews()
        assert len(due) == 2
        assert due[0].id == "two-sum"  # older first
        assert due[1].id == "valid-parens"


class TestGetNextReviewDate:
    def test_no_schedule_returns_none(self):
        assert database.get_next_review_date("two-sum") is None

    def test_returns_scheduled_date(self):
        database.update_review_schedule("two-sum", success=True)
        expected = (date.today() + timedelta(days=1)).isoformat()
        assert database.get_next_review_date("two-sum") == expected


class TestGetReviewStats:
    def test_empty_stats(self):
        stats = database.get_review_stats()
        assert stats["due_today"] == 0
        assert stats["total_reviewed"] == 0
        assert stats["avg_success_rate"] == 0
        assert stats["current_streak"] == 0

    def test_due_today_counted(self):
        database.update_review_schedule("two-sum", success=True)
        today = date.today().isoformat()
        with database.get_connection() as conn:
            conn.execute(
                "UPDATE review_schedule SET next_review_date = ? WHERE problem_id = ?",
                (today, "two-sum"),
            )

        stats = database.get_review_stats()
        assert stats["due_today"] == 1

    def test_streak_counts_consecutive_days(self):
        # Mark reviewed today and yesterday
        today = date.today()
        database.update_review_schedule("two-sum", success=True)
        with database.get_connection() as conn:
            conn.execute(
                "UPDATE review_schedule SET last_reviewed = ? WHERE problem_id = ?",
                (today.isoformat(), "two-sum"),
            )
            # Add another entry for yesterday
            conn.execute(
                "INSERT INTO review_schedule (problem_id, next_review_date, interval_days, last_reviewed) "
                "VALUES (?, ?, ?, ?)",
                ("valid-parens", (today + timedelta(days=3)).isoformat(), 3, (today - timedelta(days=1)).isoformat()),
            )

        stats = database.get_review_stats()
        assert stats["current_streak"] == 2

    def test_success_rate_calculated(self):
        database.save_submission("two-sum", "code1", "python", "Good", True)
        database.save_submission("two-sum", "code2", "python", "Bad", False)
        database.save_submission("two-sum", "code3", "python", "Good", True)

        stats = database.get_review_stats()
        assert stats["avg_success_rate"] == 67  # 2/3 = 66.67 -> 67


class TestGetSuccessRate:
    def test_no_submissions(self):
        passed, total = database.get_success_rate("two-sum")
        assert passed == 0
        assert total == 0

    def test_mixed_results(self):
        database.save_submission("two-sum", "code", "python", "Good", True)
        database.save_submission("two-sum", "code", "python", "Bad", False)

        passed, total = database.get_success_rate("two-sum")
        assert passed == 1
        assert total == 2

    def test_ungraded_not_counted(self):
        database.save_submission("two-sum", "code", "python")  # no passed value

        passed, total = database.get_success_rate("two-sum")
        assert passed == 0
        assert total == 0


class TestGetReviewInfoForProblems:
    def test_empty_list(self):
        assert database.get_review_info_for_problems([]) == {}

    def test_returns_scheduled_info(self):
        database.update_review_schedule("two-sum", success=True)

        info = database.get_review_info_for_problems(["two-sum", "valid-parens"])
        assert "two-sum" in info
        assert "valid-parens" not in info
        assert info["two-sum"]["interval_days"] == 1
