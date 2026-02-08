import json

import pytest

from src import database
from src.models import Problem


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
            "description": "Find two numbers.",
            "difficulty": "easy",
            "tags": ["arrays", "hash-table"],
        },
        {
            "id": "reverse-string",
            "title": "Reverse String",
            "description": "Reverse a string.",
            "difficulty": "easy",
            "tags": ["strings", "two-pointers"],
        },
        {
            "id": "three-sum",
            "title": "3Sum",
            "description": "Find three numbers.",
            "difficulty": "medium",
            "tags": ["arrays", "two-pointers", "sorting"],
        },
        {
            "id": "number-of-islands",
            "title": "Number of Islands",
            "description": "Count islands.",
            "difficulty": "medium",
            "tags": ["graphs", "dfs", "bfs"],
        },
        {
            "id": "merge-k-sorted-lists",
            "title": "Merge K Sorted Lists",
            "description": "Merge k lists.",
            "difficulty": "hard",
            "tags": ["linked-list", "heap"],
        },
    ]
    problems_file = tmp_path / "problems.json"
    problems_file.write_text(json.dumps(problems))
    monkeypatch.setattr(database, "PROBLEMS_JSON", problems_file)

    # No additional file by default
    monkeypatch.setattr(database, "ADDITIONAL_PROBLEMS_JSON", tmp_path / "additional.json")

    database.init_db()
    database.load_problems_from_json()
    return tmp_path


class TestGetRandomProblemWithTags:
    def test_single_tag(self):
        for _ in range(10):
            p = database.get_random_problem(tags=["arrays"])
            assert p is not None
            assert "arrays" in p.tags

    def test_multiple_tags_and_logic(self):
        p = database.get_random_problem(tags=["arrays", "two-pointers"])
        assert p is not None
        # Only three-sum has both arrays and two-pointers
        assert p.id == "three-sum"

    def test_tag_with_difficulty(self):
        p = database.get_random_problem(difficulty="easy", tags=["arrays"])
        assert p is not None
        assert p.id == "two-sum"

    def test_no_match_returns_none(self):
        p = database.get_random_problem(tags=["nonexistent-tag"])
        assert p is None

    def test_no_match_combo_returns_none(self):
        p = database.get_random_problem(difficulty="hard", tags=["arrays"])
        assert p is None


class TestListProblemsWithTags:
    def test_single_tag(self):
        problems = database.list_problems(tags=["arrays"])
        ids = {p.id for p in problems}
        assert ids == {"two-sum", "three-sum"}

    def test_multiple_tags(self):
        problems = database.list_problems(tags=["arrays", "two-pointers"])
        assert len(problems) == 1
        assert problems[0].id == "three-sum"

    def test_tag_with_difficulty(self):
        problems = database.list_problems(difficulty="easy", tags=["arrays"])
        assert len(problems) == 1
        assert problems[0].id == "two-sum"

    def test_no_match(self):
        problems = database.list_problems(tags=["nonexistent"])
        assert problems == []

    def test_no_tags_returns_all(self):
        problems = database.list_problems()
        assert len(problems) == 5


class TestGetAllTags:
    def test_returns_all_tags_with_counts(self):
        tags = database.get_all_tags()
        assert tags["arrays"] == 2  # two-sum, three-sum
        assert tags["two-pointers"] == 2  # reverse-string, three-sum
        assert tags["graphs"] == 1
        assert tags["heap"] == 1

    def test_sorted_by_count_desc(self):
        tags = database.get_all_tags()
        counts = list(tags.values())
        assert counts == sorted(counts, reverse=True)

    def test_empty_db(self, tmp_path, monkeypatch):
        # Use a fresh db with no problems
        fresh_db = tmp_path / "fresh.db"
        monkeypatch.setattr(database, "DB_PATH", fresh_db)
        database.init_db()
        tags = database.get_all_tags()
        assert tags == {}


class TestLoadAllProblems:
    def test_loads_both_files(self, tmp_path, monkeypatch):
        additional = [
            {
                "id": "climbing-stairs",
                "title": "Climbing Stairs",
                "description": "Climb stairs.",
                "difficulty": "easy",
                "tags": ["dynamic-programming"],
            },
        ]
        additional_file = tmp_path / "additional.json"
        additional_file.write_text(json.dumps(additional))
        monkeypatch.setattr(database, "ADDITIONAL_PROBLEMS_JSON", additional_file)

        # Re-init to clear, then load all
        fresh_db = tmp_path / "both.db"
        monkeypatch.setattr(database, "DB_PATH", fresh_db)
        database.init_db()
        count = database.load_all_problems()

        # 5 from problems.json + 1 from additional.json
        assert count == 6
        assert database.get_problem("climbing-stairs") is not None
        assert database.get_problem("two-sum") is not None

    def test_missing_additional_file_ok(self, tmp_path, monkeypatch):
        # Point to non-existent additional file
        monkeypatch.setattr(database, "ADDITIONAL_PROBLEMS_JSON", tmp_path / "nope.json")

        fresh_db = tmp_path / "only_main.db"
        monkeypatch.setattr(database, "DB_PATH", fresh_db)
        database.init_db()
        count = database.load_all_problems()
        assert count == 5  # Only main file
