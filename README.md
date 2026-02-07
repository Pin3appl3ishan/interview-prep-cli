# Interview Prep CLI

A terminal-based coding interview preparation tool with AI-powered code review and spaced repetition scheduling.

Built for developers who want to systematically practice DSA problems, get instant feedback on their solutions, and retain what they learn through scientifically-backed review intervals within their favorite IDE.

## Features

- **46 Curated Problems** across arrays, graphs, trees, dynamic programming, strings, and linked lists
- **AI Code Review** via Google Gemini -- get feedback on correctness, complexity, and improvements in seconds
- **Spaced Repetition** -- adaptive scheduling that increases intervals when you succeed and resets when you struggle
- **Topic Filtering** -- focus practice on specific tags like `graphs`, `dp`, or `two-pointers`
- **Progress Tracking** -- success rates, review streaks, and per-problem history
- **Rich Terminal UI** -- syntax highlighting, color-coded difficulty, and formatted panels via Rich

## Installation

**Prerequisites:** Python 3.10+, pip

```bash
# Clone and enter the project
git clone https://github.com/yourusername/interview-prep-cli.git
cd interview-prep-cli

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install
pip install -e .
```

**Set up AI review** (optional -- everything else works without it):

1. Get a free API key at https://aistudio.google.com/apikey
2. Copy the example env file and add your key:

```bash
cp .env.example .env
# Edit .env: GOOGLE_API_KEY=your_key_here
```

**Initialize the problem database:**

```bash
prep init
```

## Quick Start

```bash
# See what topics are available
prep tags

# Get a random problem to solve
prep random --tags arrays --difficulty medium

# Read a specific problem
prep show two-sum

# Write your solution, then submit for AI review
prep submit two-sum solution.py

# The CLI prompts you to mark your result, or do it manually:
prep mark two-sum solved

# Check what's due for review today
prep review

# See your overall progress
prep stats
```

### Example Session

```
$ prep review
╭─── Due for Review (2 problems) ──────────────╮
│                                               │
│  1. Two Sum (easy)                            │
│     Last reviewed: 3 days ago                 │
│     Success rate: 2/3                         │
│                                               │
│  2. Valid Parentheses (easy)                  │
│     Last reviewed: 5 days ago                 │
│     Success rate: 1/2                         │
│                                               │
╰───────────────────────────────────────────────╯

$ prep submit two-sum solution.py
╭─── Two Sum  EASY ────────────────────────────╮
│                                               │
│   1 │ def two_sum(nums, target):              │
│   2 │     seen = {}                           │
│   3 │     for i, n in enumerate(nums):        │
│   4 │         if target - n in seen:          │
│   5 │             return [seen[target-n], i]  │
│   6 │         seen[n] = i                     │
│                                               │
╰───────────────────────────────────────────────╯

  Result: PASSED
  Time: O(n)  |  Space: O(n)

╭─── AI Review ────────────────────────────────╮
│                                               │
│  Excellent solution! You correctly used a     │
│  hash map for O(n) lookup...                  │
│                                               │
╰───────────────────────────────────────────────╯

Mark this attempt? [s]olved / [struggled] / [skip]: s
  ✓ Great! Next review: February 10 (3 days)
```

## Commands

### Problem Discovery

| Command | Description |
|---------|-------------|
| `prep list` | List all problems (supports `--difficulty`, `--tags`) |
| `prep tags` | Show all topic tags with problem counts |
| `prep random` | Pick a random problem (supports `--difficulty`, `--tags`) |
| `prep show <id>` | Display a specific problem |

### Practice and Review

| Command | Description |
|---------|-------------|
| `prep submit <id> <file>` | Submit a solution for AI review |
| `prep mark <id> solved\|struggled` | Record your result and schedule next review |
| `prep review` | Show problems due for review today |
| `prep history <id>` | View past submissions (`--detailed` for full feedback) |

### Progress

| Command | Description |
|---------|-------------|
| `prep stats` | Overall statistics, review counts, streak, success rate |
| `prep init` | Initialize database and load all problems |

### Filtering Options

Both `prep list` and `prep random` accept:

- `--difficulty` / `-d` -- filter by `easy`, `medium`, or `hard`
- `--tags` / `-t` -- filter by topic (comma-separated, AND logic)

```bash
prep list --difficulty medium --tags "arrays,two-pointers"
prep random -t graphs -d hard
```

## How It Works

### Spaced Repetition

The review scheduler uses a simplified SM-2 algorithm:

| Consecutive Successes | Next Review |
|----------------------|-------------|
| 1st | 1 day |
| 2nd | 3 days |
| 3rd | 7 days |
| 4th+ | Previous interval x2 |
| Any struggle | Reset to 1 day |

Problems that are easy for you gradually disappear from your daily queue. Problems you find difficult keep coming back until they stick.

### AI Code Review

When you run `prep submit`, your solution is sent to Google Gemini along with the problem description. The AI evaluates:

1. **Correctness** -- does the solution handle the problem and edge cases?
2. **Complexity** -- time and space analysis
3. **Improvements** -- specific, actionable suggestions

All reviews are stored locally in SQLite so you can revisit them with `prep history`.

## Problem Coverage

46 problems across 6 core categories:

| Category | Count | Difficulty Range |
|----------|-------|-----------------|
| Arrays | 14 | Easy -- Hard |
| Strings | 11 | Easy -- Hard |
| Dynamic Programming | 11 | Easy -- Hard |
| Trees | 7 | Easy -- Hard |
| Graphs | 6 | Medium -- Hard |
| Linked Lists | 6 | Easy -- Hard |

25+ tags available for fine-grained filtering: `arrays`, `hash-table`, `two-pointers`, `sliding-window`, `binary-search`, `dfs`, `bfs`, `dynamic-programming`, `backtracking`, `trees`, `graphs`, `linked-list`, `sorting`, `heap`, `stack`, `queue`, and more.

Run `prep tags` to see the full list with counts.

## Project Structure

```
interview-prep-cli/
├── src/
│   ├── cli.py            # Typer command definitions and Rich UI
│   ├── database.py       # SQLite schema, queries, spaced repetition logic
│   ├── models.py         # Problem and Submission dataclasses
│   ├── ai_reviewer.py    # Google Gemini integration
│   └── __init__.py
├── data/
│   ├── problems.json              # Core problem set (15)
│   └── additional_problems.json   # Extended problem set (31)
├── tests/
│   ├── test_database.py   # DB operations and queries
│   ├── test_review.py     # Spaced repetition scheduling
│   └── test_tags.py       # Tag filtering and problem loading
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| CLI Framework | [Typer](https://typer.tiangolo.com/) |
| Terminal UI | [Rich](https://rich.readthedocs.io/) |
| Database | SQLite (local, zero-config) |
| AI | [Google Gemini](https://ai.google.dev/) (free tier: 1,500 req/day) |
| Testing | pytest (53 tests) |

## Testing

```bash
pytest tests/ -v
```

53 tests covering database operations, spaced repetition interval logic, tag filtering, and problem loading. All tests use isolated temp databases via pytest fixtures.

### Adding Problems

Add entries to `data/additional_problems.json`:

```json
{
  "id": "my-problem",
  "title": "My Problem",
  "difficulty": "medium",
  "tags": ["arrays", "hash-table"],
  "description": "Problem statement with examples and constraints..."
}
```

Then run `prep init` to load them into the database.

## Roadmap

- [ ] Timed mock interview sessions
- [ ] Progress export to Markdown/PDF
- [ ] Multi-language support (JavaScript, Java, C++)
- [ ] Daily review reminders
- [ ] Import problems from external sources

## License

MIT License. Copyright (c) 2026 Ishan Shrestha.

---

Problem descriptions inspired by [LeetCode](https://leetcode.com/). AI review powered by [Google Gemini](https://ai.google.dev/). Built with [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/).
