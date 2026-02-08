from datetime import date, datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from . import ai_reviewer, database
from .models import Problem

app = typer.Typer(help="CLI tool for coding interview preparation.")
console = Console()

DIFFICULTY_COLORS = {"easy": "green", "medium": "yellow", "hard": "red"}


def _difficulty_text(difficulty: str) -> Text:
    color = DIFFICULTY_COLORS.get(difficulty, "white")
    return Text(difficulty.upper(), style=f"bold {color}")


def _display_problem(problem: Problem):
    difficulty = _difficulty_text(problem.difficulty)
    tags = " ".join(f"[dim]\\[{t}][/dim]" for t in problem.tags)

    header = Text()
    header.append(problem.title, style="bold")
    header.append("  ")
    header.append_text(difficulty)

    body = f"{tags}\n\n{problem.description}" if tags else problem.description

    console.print()
    console.print(Panel(body, title=header, title_align="left", border_style="blue", padding=(1, 2)))
    console.print(f"  [dim]Problem ID: {problem.id}[/dim]\n")


@app.command()
def init():
    """Initialize the database and load sample problems."""
    try:
        database.init_db()
        count = database.load_all_problems()
        console.print(
            Panel(
                f"[green]Database initialized successfully![/green]\n"
                f"Loaded [bold]{count}[/bold] new problem(s).",
                title="Setup Complete",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]Error during initialization:[/red] {e}")
        raise typer.Exit(code=1)


def _parse_tags(tags: str | None) -> list[str] | None:
    """Parse comma-separated tags string into a list."""
    if not tags:
        return None
    return [t.strip() for t in tags.split(",") if t.strip()]


@app.command()
def random(
    difficulty: Optional[str] = typer.Option(
        None, "--difficulty", "-d", help="Filter by difficulty: easy, medium, hard"
    ),
    tags: Optional[str] = typer.Option(
        None, "--tags", "-t", help="Filter by tags (comma-separated, AND logic)"
    ),
):
    """Get a random problem to practice.

    Examples:
      prep random                              # Any problem
      prep random -d easy                      # Easy only
      prep random --tags arrays                # Array problems
      prep random --tags "arrays,hash-table"   # Must have both tags
      prep random -d medium --tags dp          # Medium DP problems
    """
    if difficulty and difficulty not in DIFFICULTY_COLORS:
        console.print(f"[red]Invalid difficulty:[/red] {difficulty}. Choose from: easy, medium, hard")
        raise typer.Exit(code=1)

    tag_list = _parse_tags(tags)
    problem = database.get_random_problem(difficulty, tag_list)
    if not problem:
        filters = []
        if difficulty:
            filters.append(f"difficulty='{difficulty}'")
        if tag_list:
            filters.append(f"tags={','.join(tag_list)}")
        filter_str = " with " + ", ".join(filters) if filters else ""
        console.print(f"[yellow]No problems found{filter_str}. Run [bold]prep init[/bold] or adjust filters.[/yellow]")
        raise typer.Exit(code=1)

    _display_problem(problem)


@app.command("list")
def list_problems(
    difficulty: Optional[str] = typer.Option(
        None, "--difficulty", "-d", help="Filter by difficulty: easy, medium, hard"
    ),
    tags: Optional[str] = typer.Option(
        None, "--tags", "-t", help="Filter by tags (comma-separated, AND logic)"
    ),
):
    """List all available problems."""
    if difficulty and difficulty not in DIFFICULTY_COLORS:
        console.print(f"[red]Invalid difficulty:[/red] {difficulty}. Choose from: easy, medium, hard")
        raise typer.Exit(code=1)

    tag_list = _parse_tags(tags)
    problems = database.list_problems(difficulty, tag_list)
    if not problems:
        console.print("[yellow]No problems found. Run [bold]prep init[/bold] first.[/yellow]")
        raise typer.Exit(code=1)

    table = Table(title="Interview Problems", border_style="blue")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Difficulty")
    table.add_column("Review", no_wrap=True)
    table.add_column("Tags", style="dim")

    # Fetch review info for all problems in one query
    review_info = database.get_review_info_for_problems([p.id for p in problems])
    today = date.today()

    for p in problems:
        diff_text = _difficulty_text(p.difficulty)
        tags = ", ".join(p.tags)

        info = review_info.get(p.id)
        if info:
            next_date = date.fromisoformat(info["next_review_date"])
            if next_date <= today:
                review_str = Text("🔥 Due", style="bold red")
            elif (next_date - today).days <= 3:
                review_str = Text(f"⏰ {next_date.strftime('%b %d')}", style="yellow")
            elif info["interval_days"] >= 14:
                review_str = Text("✓ Mastered", style="green")
            else:
                review_str = Text(f"  {next_date.strftime('%b %d')}", style="dim")
        else:
            review_str = Text("—", style="dim")

        table.add_row(p.id, p.title, diff_text, review_str, tags)

    console.print()
    console.print(table)
    console.print(f"\n  [dim]{len(problems)} problem(s) total[/dim]\n")


@app.command()
def tags():
    """Show all available tags with problem counts."""
    tag_counts = database.get_all_tags()
    if not tag_counts:
        console.print("[yellow]No tags found. Run [bold]prep init[/bold] first.[/yellow]")
        raise typer.Exit(code=1)

    lines = []
    for tag, count in tag_counts.items():
        lines.append(f"  [cyan]{tag}[/cyan] ({count} problem{'s' if count != 1 else ''})")

    console.print()
    console.print(Panel(
        "\n".join(lines),
        title="Available Tags",
        border_style="blue",
        padding=(1, 2),
    ))
    console.print(f"  [dim]Use [bold]prep list --tags <tag>[/bold] to filter by tag[/dim]\n")


@app.command()
def show(problem_id: str = typer.Argument(help="The problem ID to display")):
    """Show a specific problem by ID."""
    problem = database.get_problem(problem_id)
    if not problem:
        console.print(f"[red]Problem not found:[/red] {problem_id}")
        console.print("[dim]Run [bold]prep list[/bold] to see available problem IDs.[/dim]")
        raise typer.Exit(code=1)

    _display_problem(problem)


@app.command()
def stats():
    """Show your practice statistics."""
    try:
        data = database.get_stats()
    except Exception:
        console.print("[yellow]No stats available. Run [bold]prep init[/bold] first.[/yellow]")
        raise typer.Exit(code=1)

    table = Table(title="Practice Statistics", border_style="blue")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total Problems", str(data["total_problems"]))
    for diff in ("easy", "medium", "hard"):
        count = data["by_difficulty"].get(diff, 0)
        color = DIFFICULTY_COLORS[diff]
        table.add_row(f"  [{color}]{diff.capitalize()}[/{color}]", str(count))

    table.add_row("", "")
    table.add_row("Total Submissions", str(data["total_submissions"]))
    table.add_row("Problems Attempted", str(data["problems_attempted"]))

    # Review stats
    try:
        review_data = database.get_review_stats()
        table.add_row("", "")
        table.add_row("Due for Review Today", str(review_data["due_today"]))
        table.add_row("Total Reviewed", str(review_data["total_reviewed"]))
        table.add_row("Average Success Rate", f"{review_data['avg_success_rate']}%")
        streak = review_data["current_streak"]
        streak_str = f"{streak} day{'s' if streak != 1 else ''}" if streak > 0 else "0 days"
        table.add_row("Current Streak", streak_str)
    except Exception:
        pass  # review_schedule table may not exist yet

    console.print()
    console.print(table)
    console.print()


@app.command()
def submit(
    problem_id: str = typer.Argument(help="The problem ID to submit a solution for"),
    file_path: str = typer.Argument(help="Path to the solution file"),
):
    """Submit a solution for AI-powered code review."""
    problem = database.get_problem(problem_id)
    if not problem:
        console.print(f"[red]Problem not found:[/red] {problem_id}")
        console.print("[dim]Run [bold]prep list[/bold] to see available problem IDs.[/dim]")
        raise typer.Exit(code=1)

    path = Path(file_path)
    if not path.is_file():
        console.print(f"[red]File not found:[/red] {file_path}")
        raise typer.Exit(code=1)

    code = path.read_text(encoding="utf-8")
    language = "python" if path.suffix in (".py", "") else path.suffix.lstrip(".")

    # Display the submitted code
    header = Text()
    header.append(problem.title, style="bold")
    header.append("  ")
    header.append_text(_difficulty_text(problem.difficulty))

    console.print()
    console.print(Panel(
        Syntax(code, language, theme="monokai", line_numbers=True),
        title=header,
        title_align="left",
        border_style="blue",
        padding=(1, 2),
    ))

    # Call AI reviewer
    try:
        with console.status("[bold blue]Reviewing your code..."):
            result = ai_reviewer.review_code(problem, code, language)
    except ValueError as e:
        console.print(f"\n[red]{e}[/red]")
        database.save_submission(problem_id, code, language)
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"\n[red]API error:[/red] {e}")
        database.save_submission(problem_id, code, language)
        console.print("[dim]Submission saved without AI feedback.[/dim]")
        raise typer.Exit(code=1)

    # Save to database
    database.save_submission(
        problem_id=problem_id,
        code=code,
        language=language,
        ai_feedback=result["feedback"],
        passed=result["passed"],
    )

    # Display results
    passed = result["passed"]
    badge = "[bold green]PASSED[/bold green]" if passed else "[bold red]NEEDS WORK[/bold red]"

    console.print(f"\n  Result: {badge}")
    console.print(f"  [dim]Time: {result['time_complexity']}  |  Space: {result['space_complexity']}[/dim]\n")

    console.print(Panel(
        Markdown(result["feedback"]),
        title="AI Review",
        title_align="left",
        border_style="green" if passed else "red",
        padding=(1, 2),
    ))

    # Offer to mark the problem for spaced repetition
    try:
        choice = Prompt.ask(
            "\n  Mark this attempt?",
            choices=["s", "struggled", "skip"],
            default="s" if passed else "struggled",
        )
        if choice == "skip":
            console.print()
        elif choice == "s":
            info = database.update_review_schedule(problem_id, success=True)
            console.print(f"  [green]✓ Great![/green] Next review: [bold]{info['next_review_date'].strftime('%B %d')}[/bold] ({info['interval_days']} days)\n")
        else:
            info = database.update_review_schedule(problem_id, success=False)
            console.print(f"  [yellow]✗ No worries![/yellow] Next review: [bold]{info['next_review_date'].strftime('%B %d')}[/bold] (1 day)\n")
    except (KeyboardInterrupt, EOFError):
        console.print("\n")


@app.command()
def history(
    problem_id: str = typer.Argument(help="The problem ID to view history for"),
    detailed: bool = typer.Option(False, "--detailed", "-v", help="Show full feedback for each submission"),
):
    """View past submissions for a problem."""
    problem = database.get_problem(problem_id)
    if not problem:
        console.print(f"[red]Problem not found:[/red] {problem_id}")
        console.print("[dim]Run [bold]prep list[/bold] to see available problem IDs.[/dim]")
        raise typer.Exit(code=1)

    submissions = database.get_submissions(problem_id)
    if not submissions:
        console.print(f"[yellow]No submissions yet for [bold]{problem.title}[/bold].[/yellow]")
        console.print(f"[dim]Run [bold]prep submit {problem_id} <file>[/bold] to submit a solution.[/dim]")
        raise typer.Exit()

    header = Text()
    header.append(f"History: {problem.title}", style="bold")
    header.append("  ")
    header.append_text(_difficulty_text(problem.difficulty))
    console.print()

    if detailed:
        for i, sub in enumerate(submissions, 1):
            passed_str = "[green]Passed[/green]" if sub.passed else "[red]Needs Work[/red]" if sub.passed is not None else "[dim]No review[/dim]"
            console.print(f"  [bold]#{i}[/bold]  {sub.submitted_at}  {passed_str}")

            if sub.ai_feedback:
                console.print(Panel(
                    Markdown(sub.ai_feedback),
                    border_style="dim",
                    padding=(1, 2),
                ))
            else:
                console.print("  [dim]No AI feedback available.[/dim]\n")
    else:
        table = Table(title=header, border_style="blue")
        table.add_column("#", style="bold", width=4)
        table.add_column("Date", style="cyan")
        table.add_column("Result")
        table.add_column("Feedback", style="dim")

        for i, sub in enumerate(submissions, 1):
            if sub.passed is True:
                result_str = Text("Passed", style="green")
            elif sub.passed is False:
                result_str = Text("Needs Work", style="red")
            else:
                result_str = Text("No review", style="dim")

            preview = ""
            if sub.ai_feedback:
                preview = sub.ai_feedback[:60] + ("..." if len(sub.ai_feedback) > 60 else "")

            date_str = str(sub.submitted_at)[:19] if sub.submitted_at else ""
            table.add_row(str(i), date_str, result_str, preview)

        console.print(table)
        console.print(f"\n  [dim]{len(submissions)} submission(s)[/dim]\n")


@app.command()
def mark(
    problem_id: str = typer.Argument(help="The problem ID to mark"),
    result: str = typer.Argument(help="Result: solved (or ✓) / struggled (or ✗)"),
):
    """Mark a problem as solved or struggled to update review schedule."""
    problem = database.get_problem(problem_id)
    if not problem:
        console.print(f"[red]Problem not found:[/red] {problem_id}")
        console.print("[dim]Run [bold]prep list[/bold] to see available problem IDs.[/dim]")
        raise typer.Exit(code=1)

    result_lower = result.lower()
    if result_lower in ("solved", "✓", "s"):
        success = True
    elif result_lower in ("struggled", "✗", "x", "f"):
        success = False
    else:
        console.print(f"[red]Invalid result:[/red] {result}")
        console.print("[dim]Use: solved (✓) or struggled (✗)[/dim]")
        raise typer.Exit(code=1)

    info = database.update_review_schedule(problem_id, success)
    next_date = info["next_review_date"]
    interval = info["interval_days"]

    if success:
        console.print(f"\n  [green]✓ Marked as solved![/green]")
    else:
        console.print(f"\n  [yellow]✗ Marked as struggled.[/yellow]")

    console.print(f"  Next review: [bold]{next_date.strftime('%B %d, %Y')}[/bold] ({interval} day{'s' if interval != 1 else ''})\n")


@app.command()
def review():
    """Show problems due for review today."""
    due = database.get_due_reviews()

    if not due:
        console.print("\n  [green]No problems due for review today! 🎉[/green]")
        console.print("  [dim]Use [bold]prep mark <problem-id> solved[/bold] to schedule reviews.[/dim]\n")
        return

    lines = []
    for i, problem in enumerate(due, 1):
        diff_color = DIFFICULTY_COLORS.get(problem.difficulty, "white")
        passed, total = database.get_success_rate(problem.id)

        review_info = database.get_next_review_date(problem.id)
        # Get last_reviewed from review_info_for_problems
        review_details = database.get_review_info_for_problems([problem.id]).get(problem.id)
        last_reviewed = review_details["last_reviewed"] if review_details and review_details["last_reviewed"] else None

        if last_reviewed:
            last_date = date.fromisoformat(last_reviewed)
            days_ago = (date.today() - last_date).days
            if days_ago == 0:
                last_str = "Today"
            elif days_ago == 1:
                last_str = "1 day ago"
            else:
                last_str = f"{days_ago} days ago"
            last_line = f"Last reviewed: {last_str}"
        else:
            last_line = "Never reviewed"

        rate_line = f"Success rate: {passed}/{total}" if total > 0 else ""

        entry = f"[bold]{i}. {problem.title}[/bold] ([{diff_color}]{problem.difficulty}[/{diff_color}])\n   [dim]{last_line}[/dim]"
        if rate_line:
            entry += f"\n   [dim]{rate_line}[/dim]"
        lines.append(entry)

    body = "\n\n".join(lines)
    console.print()
    console.print(Panel(
        body,
        title=f"Due for Review ({len(due)} problem{'s' if len(due) != 1 else ''})",
        border_style="yellow",
        padding=(1, 2),
    ))
    console.print("  [dim]Use [bold]prep show <problem-id>[/bold] to practice[/dim]\n")


if __name__ == "__main__":
    app()
