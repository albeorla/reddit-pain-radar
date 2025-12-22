"""Pipeline command - run the full mining pipeline."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from langchain_openai import ChatOpenAI
from rich.table import Table

from ..config import get_settings
from ..logging_config import configure_logging, get_logger
from ..pipeline import run_pipeline, run_process_only
from ..progress import create_progress, set_progress
from ..store import AsyncStore
from . import app, console


@app.command()
def run(
    subreddits: Annotated[
        list[str] | None,
        typer.Option(
            "--subreddit",
            "-s",
            help="Subreddits to mine (can specify multiple). Overrides source sets.",
        ),
    ] = None,
    source_set: Annotated[
        int | None,
        typer.Option(
            "--source-set",
            "-S",
            help="Source set ID to use.",
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum posts per subreddit to fetch.",
        ),
    ] = None,
    process_limit: Annotated[
        int | None,
        typer.Option(
            "--process-limit",
            "-p",
            help="Maximum posts to process with AI.",
        ),
    ] = None,
    skip_fetch: Annotated[
        bool,
        typer.Option(
            "--skip-fetch",
            help="Skip fetching new posts, only process existing unprocessed posts.",
        ),
    ] = False,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            help="Logging level: DEBUG, INFO, WARNING, ERROR",
        ),
    ] = "INFO",
    log_json: Annotated[
        bool,
        typer.Option(
            "--log-json",
            help="Output logs as JSON.",
        ),
    ] = False,
    no_progress: Annotated[
        bool,
        typer.Option(
            "--no-progress",
            help="Disable progress bars (useful for logging).",
        ),
    ] = False,
    db_path: Annotated[
        str | None,
        typer.Option(
            "--db",
            help="Path to database file.",
        ),
    ] = None,
):
    """Run the full pain signal pipeline.

    Uses source sets by default. Add source sets with: pain-radar sources-add <preset>
    """
    configure_logging(log_level, log_json)
    logger = get_logger(__name__)

    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        console.print("\nMake sure you have a .env file with:")
        console.print("  OPENAI_API_KEY=sk-...")
        raise typer.Exit(1) from e

    path = db_path or settings.db_path
    run_subreddits = []
    fetch_limit = limit or settings.posts_per_subreddit

    # Determine subreddits to use
    if subreddits:
        # Explicit subreddits override everything
        run_subreddits = list(subreddits)
    elif source_set:
        # Use specific source set
        async def _get_source_set():
            store = AsyncStore(path)
            await store.connect()
            ss = await store.get_source_set(source_set)
            await store.close()
            return ss

        ss = asyncio.run(_get_source_set())
        if not ss:
            console.print(f"[red]Source set {source_set} not found[/red]")
            raise typer.Exit(1)
        run_subreddits = ss["subreddits"]
        fetch_limit = limit or ss.get("limit_per_sub", settings.posts_per_subreddit)
        console.print(f"Using source set: [bold]{ss['name']}[/bold]")
    else:
        # Use all active source sets
        async def _get_all_subreddits():
            store = AsyncStore(path)
            await store.connect()
            subs = await store.get_all_active_subreddits()
            await store.close()
            return subs

        run_subreddits = asyncio.run(_get_all_subreddits())

        if not run_subreddits:
            console.print("[yellow]No active source sets found.[/yellow]")
            console.print("Add one with: [cyan]pain-radar sources-add indie_saas[/cyan]")
            raise typer.Exit(1)

    # Create LLM
    if not settings.openai_api_key:
        console.print("[red]Error:[/red] OPENAI_API_KEY not set")
        raise typer.Exit(1)

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )

    console.print(f"\n[bold]Pain Radar[/bold] - Scanning {len(run_subreddits)} subreddits")
    console.print(f"  Subreddits: {', '.join(run_subreddits[:5])}", end="")
    if len(run_subreddits) > 5:
        console.print(f" (+{len(run_subreddits) - 5} more)")
    else:
        console.print()
    console.print(f"  Posts per subreddit: {fetch_limit}")
    console.print(f"  Model: {settings.openai_model}")
    console.print()

    # Create a settings-like object for the pipeline
    class RunSettings:
        def __init__(self):
            self.subreddits = run_subreddits
            self.listing = settings.listing
            self.posts_per_subreddit = fetch_limit
            self.top_comments = settings.top_comments
            self.max_concurrency = settings.max_concurrency
            self.db_path = path
            self.user_agent = settings.user_agent
            self.openai_api_key = settings.openai_api_key
            self.openai_model = settings.openai_model

    run_settings = RunSettings()

    async def _run():
        if skip_fetch:
            return await run_process_only(run_settings, llm, process_limit)
        else:
            return await run_pipeline(run_settings, llm, fetch_new=True, process_limit=process_limit)

    try:
        # Use progress bars unless disabled or logging JSON
        if no_progress or log_json:
            result = asyncio.run(_run())
        else:
            # Run with progress display
            progress = create_progress()
            with progress:
                set_progress(progress)
                result = asyncio.run(_run())
                set_progress(None)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise typer.Exit(130) from None
    except Exception as e:
        logger.exception("pipeline_failed")
        console.print(f"\n[red]Pipeline failed:[/red] {e}")
        raise typer.Exit(1) from e

    # Display results
    console.print(f"\n[green]✓ Pipeline complete[/green] (Run #{result.run_id})")
    console.print(f"  Posts fetched: {result.posts_fetched}")
    console.print(f"  Posts analyzed: {result.posts_analyzed}")
    console.print(f"  Signals saved: {result.signals_saved}")
    console.print(f"  Qualified: {result.qualified_signals}")
    console.print(f"  Errors: {result.errors}")

    if result.top_signals:
        console.print("\n[bold]Top Signals:[/bold]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Score", width=6)
        table.add_column("Signal", width=50)
        table.add_column("Subreddit", width=15)

        for sig in result.top_signals[:5]:
            summary = sig.get("signal_summary", "")
            table.add_row(
                str(sig.get("total_score", "-")),
                (summary[:47] + "...") if len(summary) > 50 else summary,
                sig.get("subreddit", ""),
            )
        console.print(table)
