from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Problem:
    id: str
    title: str
    description: str
    difficulty: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row) -> Problem:
        return cls(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            difficulty=row["difficulty"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            created_at=row["created_at"],
        )

    @classmethod
    def from_json(cls, data: dict) -> Problem:
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            difficulty=data["difficulty"],
            tags=data.get("tags", []),
        )


@dataclass
class Submission:
    id: int | None
    problem_id: str
    code: str
    language: str = "python"
    ai_feedback: str | None = None
    passed: bool | None = None
    submitted_at: datetime | None = None

    @classmethod
    def from_row(cls, row) -> Submission:
        return cls(
            id=row["id"],
            problem_id=row["problem_id"],
            code=row["code"],
            language=row["language"],
            ai_feedback=row["ai_feedback"],
            passed=bool(row["passed"]) if row["passed"] is not None else None,
            submitted_at=row["submitted_at"],
        )
