"""AI-powered code review using the Google Gemini API."""

import json
import os

import google.generativeai as genai
from dotenv import load_dotenv

from .models import Problem

load_dotenv()

REVIEW_PROMPT = """\
You are an expert coding interview reviewer. Analyze the submitted solution and provide constructive feedback.

You MUST respond with valid JSON only — no markdown, no code fences, no extra text. Use this exact schema:

{{
  "feedback": "Your detailed review (under 250 words). Be encouraging but honest. Mention what's done well, then give 1-2 specific improvements.",
  "passed": true or false,
  "time_complexity": "O(...)",
  "space_complexity": "O(...)"
}}

Rules for "passed":
- true if the solution correctly solves the problem for typical inputs
- false if there are logical errors, missing edge cases, or it doesn't solve the problem

## Problem: {title} ({difficulty})

{description}

## Submitted Solution ({language}):

```{language}
{code}
```

Evaluate:
1. Correctness — does it solve the problem?
2. Edge cases handled?
3. One specific improvement suggestion.
Be encouraging but honest.
"""


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers that Gemini sometimes adds."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence line
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def review_code(problem: Problem, code: str, language: str = "python") -> dict:
    """Submit code to Gemini for review and return structured feedback.

    Returns:
        dict with keys: feedback (str), passed (bool),
        time_complexity (str), space_complexity (str)

    Raises:
        ValueError: If GOOGLE_API_KEY is not set.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY not set. "
            "Add it to your .env file or set the environment variable.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Add your key: GOOGLE_API_KEY=AIza..."
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = REVIEW_PROMPT.format(
        title=problem.title,
        difficulty=problem.difficulty,
        description=problem.description,
        language=language,
        code=code,
    )

    response = model.generate_content(prompt)
    raw = response.text

    cleaned = _strip_markdown_fences(raw)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "feedback": raw,
            "passed": False,
            "time_complexity": "Unknown",
            "space_complexity": "Unknown",
        }

    return {
        "feedback": result.get("feedback", raw),
        "passed": bool(result.get("passed", False)),
        "time_complexity": result.get("time_complexity", "Unknown"),
        "space_complexity": result.get("space_complexity", "Unknown"),
    }
