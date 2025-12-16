"""Typer CLI for Idea Miner."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional

import typer
from langchain_openai import ChatOpenAI
from rich.console import Console
from rich.table import Table

from .config import Settings, get_settings
from .logging_config import configure_logging, get_logger
from .pipeline import run_fetch_only, run_pipeline, run_process_only
from .report import generate_json_report, generate_report
from .store import AsyncStore

app = typer.Typer(
    name="idea-miner",
    help="Mine Reddit for microSaaS and side-hustle ideas using AI.",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        from . import __version__

        console.print(f"idea-miner {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(  # noqa: ARG001
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
):
    """Idea Miner - Mine Reddit for microSaaS ideas."""
    pass


@app.command()
def run(
    subreddits: Optional[List[str]] = typer.Option(
        None,
        "--subreddit",
        "-s",
        help="Subreddits to mine (can specify multiple). Overrides config.",
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        "-l",
        help="Maximum posts per subreddit to fetch.",
    ),
    process_limit: Optional[int] = typer.Option(
        None,
        "--process-limit",
        "-p",
        help="Maximum posts to process with AI.",
    ),
    skip_fetch: bool = typer.Option(
        False,
        "--skip-fetch",
        help="Skip fetching new posts, only process existing unprocessed posts.",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="Logging level: DEBUG, INFO, WARNING, ERROR",
    ),
    log_json: bool = typer.Option(
        False,
        "--log-json",
        help="Output logs as JSON.",
    ),
):
    """Run the full idea mining pipeline.

    Fetches posts from Reddit, analyzes them with AI, and stores the results.
    """
    configure_logging(log_level, log_json)
    logger = get_logger(__name__)

    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        console.print("\nMake sure you have a .env file with:")
        console.print("  OPENAI_API_KEY=sk-...")
        raise typer.Exit(1)

    # Apply CLI overrides
    if subreddits:
        settings.subreddits = list(subreddits)
    if limit:
        settings.posts_per_subreddit = limit

    # Create LLM
    if not settings.openai_api_key:
        console.print("[red]Error:[/red] OPENAI_API_KEY not set")
        raise typer.Exit(1)

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )

    console.print(f"\n[bold]Idea Miner[/bold] - Mining {len(settings.subreddits)} subreddits")
    console.print(f"  Subreddits: {', '.join(settings.subreddits)}")
    console.print(f"  Posts per subreddit: {settings.posts_per_subreddit}")
    console.print(f"  Model: {settings.openai_model}")
    console.print()

    async def _run():
        if skip_fetch:
            return await run_process_only(settings, llm, process_limit)
        else:
            return await run_pipeline(settings, llm, fetch_new=True, process_limit=process_limit)

    try:
        result = asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        logger.exception("pipeline_failed")
        console.print(f"\n[red]Pipeline failed:[/red] {e}")
        raise typer.Exit(1)

    # Display results
    console.print(f"\n[green]✓ Pipeline complete[/green] (Run #{result.run_id})")
    console.print(f"  Posts fetched: {result.posts_fetched}")
    console.print(f"  Posts analyzed: {result.posts_analyzed}")
    console.print(f"  Ideas saved: {result.ideas_saved}")
    console.print(f"  Qualified: {result.qualified_ideas}")
    console.print(f"  Errors: {result.errors}")

    if result.top_ideas:
        console.print("\n[bold]Top Ideas:[/bold]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Score", width=6)
        table.add_column("Idea", width=50)
        table.add_column("Subreddit", width=15)

        for idea in result.top_ideas[:5]:
            table.add_row(
                str(idea.get("total_score", "-")),
                (idea.get("idea_summary", "")[:47] + "...") if len(idea.get("idea_summary", "")) > 50 else idea.get("idea_summary", ""),
                idea.get("subreddit", ""),
            )
        console.print(table)


@app.command()
def fetch(
    subreddits: Optional[List[str]] = typer.Option(
        None,
        "--subreddit",
        "-s",
        help="Subreddits to fetch (can specify multiple).",
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        "-l",
        help="Maximum posts per subreddit.",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="Logging level.",
    ),
):
    """Fetch posts from Reddit without AI processing.

    Useful for building up a corpus before running AI analysis.
    """
    configure_logging(log_level, False)

    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1)

    if subreddits:
        settings.subreddits = list(subreddits)
    if limit:
        settings.posts_per_subreddit = limit

    console.print(f"\n[bold]Fetching posts[/bold] from {len(settings.subreddits)} subreddits...")

    try:
        count = asyncio.run(run_fetch_only(settings))
        console.print(f"[green]✓ Fetched {count} posts[/green]")
    except Exception as e:
        console.print(f"[red]Fetch failed:[/red] {e}")
        raise typer.Exit(1)


@app.command(name="init-db")
def init_db(
    db_path: Optional[str] = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Initialize the database schema.

    Creates the SQLite database and tables if they don't exist.
    """
    path = db_path or "idea_miner.sqlite3"

    async def _init():
        store = AsyncStore(path)
        await store.connect()
        await store.init_db()
        await store.close()

    asyncio.run(_init())
    console.print(f"[green]✓ Database initialized:[/green] {path}")


@app.command()
def stats(
    db_path: Optional[str] = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Show database statistics."""
    path = db_path or "idea_miner.sqlite3"

    if not Path(path).exists():
        console.print(f"[red]Database not found:[/red] {path}")
        console.print("Run 'idea-miner init-db' first.")
        raise typer.Exit(1)

    async def _stats():
        store = AsyncStore(path)
        await store.connect()
        result = await store.get_stats()
        await store.close()
        return result

    result = asyncio.run(_stats())

    console.print("\n[bold]Database Statistics[/bold]")
    console.print(f"  Total posts: {result['total_posts']}")
    console.print(f"  Processed posts: {result['processed_posts']}")
    console.print(f"  Total ideas: {result['total_ideas']}")
    console.print(f"  Qualified ideas: {result['qualified_ideas']}")
    console.print(f"  Average score: {result['avg_score']}")


@app.command()
def export(
    output: str = typer.Option(
        "ideas.json",
        "--output",
        "-o",
        help="Output file path (.json or .csv).",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-l",
        help="Maximum ideas to export.",
    ),
    include_disqualified: bool = typer.Option(
        False,
        "--include-disqualified",
        help="Include disqualified ideas.",
    ),
    db_path: Optional[str] = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Export top ideas to JSON or CSV."""
    path = db_path or "idea_miner.sqlite3"

    if not Path(path).exists():
        console.print(f"[red]Database not found:[/red] {path}")
        raise typer.Exit(1)

    async def _export():
        store = AsyncStore(path)
        await store.connect()
        ideas = await store.get_top_ideas(limit=limit, include_disqualified=include_disqualified)
        await store.close()
        return ideas

    ideas = asyncio.run(_export())

    if not ideas:
        console.print("[yellow]No ideas found to export.[/yellow]")
        raise typer.Exit(0)

    output_path = Path(output)

    if output_path.suffix == ".csv":
        import csv

        with open(output_path, "w", newline="") as f:
            if ideas:
                writer = csv.DictWriter(f, fieldnames=ideas[0].keys())
                writer.writeheader()
                writer.writerows(ideas)
    else:
        with open(output_path, "w") as f:
            json.dump(ideas, f, indent=2, default=str)

    console.print(f"[green]✓ Exported {len(ideas)} ideas to:[/green] {output_path}")


@app.command()
def top(
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Number of ideas to show.",
    ),
    db_path: Optional[str] = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Show top-scored ideas."""
    path = db_path or "idea_miner.sqlite3"

    if not Path(path).exists():
        console.print(f"[red]Database not found:[/red] {path}")
        raise typer.Exit(1)

    async def _top():
        store = AsyncStore(path)
        await store.connect()
        ideas = await store.get_top_ideas(limit=limit)
        await store.close()
        return ideas

    ideas = asyncio.run(_top())

    if not ideas:
        console.print("[yellow]No ideas found.[/yellow]")
        console.print("Run 'idea-miner run' to analyze posts.")
        raise typer.Exit(0)

    table = Table(title=f"Top {len(ideas)} Ideas", show_header=True, header_style="bold")
    table.add_column("#", width=3)
    table.add_column("Score", width=6)
    table.add_column("P", width=3)  # Practicality
    table.add_column("$", width=3)  # Profitability
    table.add_column("D", width=3)  # Distribution
    table.add_column("C", width=3)  # Competition
    table.add_column("M", width=3)  # Moat
    table.add_column("Idea", width=45)
    table.add_column("Subreddit", width=12)

    for i, idea in enumerate(ideas, 1):
        summary = idea.get("idea_summary", "")
        if len(summary) > 42:
            summary = summary[:42] + "..."
        table.add_row(
            str(i),
            str(idea.get("total_score", "-")),
            str(idea.get("practicality", "-")),
            str(idea.get("profitability", "-")),
            str(idea.get("distribution", "-")),
            str(idea.get("competition", "-")),
            str(idea.get("moat", "-")),
            summary,
            idea.get("subreddit", "")[:12],
        )

    console.print(table)
    console.print("\nP=Practicality, $=Profitability, D=Distribution, C=Competition, M=Moat")


@app.command()
def report(
    run_id: Optional[int] = typer.Option(
        None,
        "--run",
        "-r",
        help="Run ID to generate report for (default: latest).",
    ),
    output_dir: str = typer.Option(
        "reports",
        "--output-dir",
        "-o",
        help="Directory to save reports.",
    ),
    json_format: bool = typer.Option(
        False,
        "--json",
        help="Generate JSON report instead of Markdown.",
    ),
    include_disqualified: bool = typer.Option(
        False,
        "--include-disqualified",
        help="Include disqualified ideas in report.",
    ),
    db_path: Optional[str] = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Generate a report from pipeline results.

    Creates a detailed Markdown or JSON report of discovered ideas,
    including scores, evidence, and validation steps.
    """
    path = db_path or "idea_miner.sqlite3"

    if not Path(path).exists():
        console.print(f"[red]Database not found:[/red] {path}")
        console.print("Run 'idea-miner run' first to analyze posts.")
        raise typer.Exit(1)

    async def _report():
        store = AsyncStore(path)
        await store.connect()
        try:
            if json_format:
                return await generate_json_report(store, run_id, output_dir)
            else:
                return await generate_report(store, run_id, output_dir, include_disqualified)
        finally:
            await store.close()

    try:
        report_path = asyncio.run(_report())
        console.print(f"[green]✓ Report generated:[/green] {report_path}")
        console.print(f"\nOpen with: [bold]cat {report_path}[/bold]")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def runs(
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Number of runs to show.",
    ),
    db_path: Optional[str] = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Show recent pipeline runs."""
    path = db_path or "idea_miner.sqlite3"

    if not Path(path).exists():
        console.print(f"[red]Database not found:[/red] {path}")
        raise typer.Exit(1)

    async def _runs():
        store = AsyncStore(path)
        await store.connect()
        result = await store.get_runs(limit=limit)
        await store.close()
        return result

    runs_list = asyncio.run(_runs())

    if not runs_list:
        console.print("[yellow]No runs found.[/yellow]")
        console.print("Run 'idea-miner run' to start analyzing posts.")
        raise typer.Exit(0)

    table = Table(title="Pipeline Runs", show_header=True, header_style="bold")
    table.add_column("ID", width=4)
    table.add_column("Started", width=19)
    table.add_column("Status", width=10)
    table.add_column("Posts", width=6)
    table.add_column("Ideas", width=6)
    table.add_column("Qualified", width=9)
    table.add_column("Report", width=20)

    for run in runs_list:
        started = run.get("started_at", "")[:19].replace("T", " ")
        report_path = run.get("report_path", "")
        if report_path:
            report_path = Path(report_path).name[:20]
        table.add_row(
            str(run.get("id", "-")),
            started,
            run.get("status", "-"),
            str(run.get("posts_fetched", "-")),
            str(run.get("ideas_saved", "-")),
            str(run.get("qualified_ideas", "-")),
            report_path or "-",
        )

    console.print(table)
    console.print("\nGenerate a report with: [bold]idea-miner report --run <ID>[/bold]")


@app.command()
def show(
    idea_id: int = typer.Argument(..., help="Idea ID to show details for."),
    db_path: Optional[str] = typer.Option(
        None,
        "--db",
        help="Path to database file.",
    ),
):
    """Show detailed information about a specific idea."""
    path = db_path or "idea_miner.sqlite3"

    if not Path(path).exists():
        console.print(f"[red]Database not found:[/red] {path}")
        raise typer.Exit(1)

    async def _show():
        store = AsyncStore(path)
        await store.connect()
        result = await store.get_idea_detail(idea_id)
        await store.close()
        return result

    idea = asyncio.run(_show())

    if not idea:
        console.print(f"[red]Idea {idea_id} not found.[/red]")
        raise typer.Exit(1)

    # Display idea details
    console.print(f"\n[bold]Idea #{idea_id}[/bold]")
    console.print(f"[dim]{'─' * 60}[/dim]")
    
    console.print(f"\n[bold]Summary:[/bold] {idea.get('idea_summary', 'N/A')}")
    console.print(f"[bold]Subreddit:[/bold] r/{idea.get('subreddit', 'N/A')}")
    console.print(f"[bold]Post:[/bold] {idea.get('post_title', 'N/A')}")
    
    if idea.get("permalink"):
        console.print(f"[bold]Link:[/bold] {idea.get('permalink')}")

    console.print(f"\n[bold]Score:[/bold] {idea.get('total_score', 0)}/50")
    if idea.get("disqualified"):
        console.print("[red]⚠ DISQUALIFIED[/red]")
    
    console.print(f"\n[bold]Dimensions:[/bold]")
    console.print(f"  Practicality:  {idea.get('practicality', '-')}/10")
    console.print(f"  Profitability: {idea.get('profitability', '-')}/10")
    console.print(f"  Distribution:  {idea.get('distribution', '-')}/10")
    console.print(f"  Competition:   {idea.get('competition', '-')}/10")
    console.print(f"  Moat:          {idea.get('moat', '-')}/10")

    if idea.get("target_user"):
        console.print(f"\n[bold]Target User:[/bold] {idea.get('target_user')}")
    if idea.get("pain_point"):
        console.print(f"[bold]Pain Point:[/bold] {idea.get('pain_point')}")
    if idea.get("proposed_solution"):
        console.print(f"[bold]Solution:[/bold] {idea.get('proposed_solution')}")

    # Evidence signals
    signals = idea.get("evidence_signals")
    if signals:
        if isinstance(signals, str):
            import json as json_module
            signals = json_module.loads(signals)
        if signals:
            console.print(f"\n[bold]Evidence:[/bold]")
            for sig in signals:
                console.print(f"  • {sig}")

    # Next steps
    next_steps = idea.get("next_validation_steps")
    if next_steps:
        if isinstance(next_steps, str):
            import json as json_module
            next_steps = json_module.loads(next_steps)
        if next_steps:
            console.print(f"\n[bold]Validation Steps:[/bold]")
            for step in next_steps:
                console.print(f"  • {step}")

    # Reasoning
    why = idea.get("why")
    if why:
        if isinstance(why, str):
            import json as json_module
            why = json_module.loads(why)
        if why:
            console.print(f"\n[bold]Reasoning:[/bold]")
            for reason in why:
                console.print(f"  • {reason}")

    console.print()


if __name__ == "__main__":
    app()
