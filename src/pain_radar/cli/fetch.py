"""Fetch command - fetch posts from Reddit without AI processing."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from ..config import get_settings
from ..logging_config import configure_logging
from ..pipeline import run_fetch_only
from ..store import AsyncStore
from . import app, console


@app.command()
def fetch(
    subreddits: Annotated[
        list[str] | None,
        typer.Option(
            "--subreddit",
            "-s",
            help="Subreddits to fetch (can specify multiple). Overrides source sets.",
        ),
    ] = None,
    source_set: Annotated[
        int | None,
        typer.Option(
            "--source-set",
            "-S",
            help="Source set ID to fetch from.",
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum posts per subreddit.",
        ),
    ] = None,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            help="Logging level.",
        ),
    ] = "INFO",
    db_path: Annotated[
        str | None,
        typer.Option(
            "--db",
            help="Path to database file.",
        ),
    ] = None,
):
    """Fetch posts from Reddit without AI processing.

    Uses source sets by default. Add source sets with: pain-radar sources-add <preset>
    """
    configure_logging(log_level, False)

    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1) from e

    path = db_path or settings.db_path
    fetch_subreddits = []
    fetch_limit = limit or settings.posts_per_subreddit

    # Determine subreddits to fetch
    if subreddits:
        # Explicit subreddits override everything
        fetch_subreddits = list(subreddits)
    elif source_set:
        # Fetch from specific source set
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
        fetch_subreddits = ss["subreddits"]
        fetch_limit = limit or ss.get("limit_per_sub", settings.posts_per_subreddit)
        console.print(f"Using source set: [bold]{ss['name']}[/bold]")
    else:
        # Fetch from all active source sets
        async def _get_all_subreddits():
            store = AsyncStore(path)
            await store.connect()
            subs = await store.get_all_active_subreddits()
            await store.close()
            return subs

        fetch_subreddits = asyncio.run(_get_all_subreddits())

        if not fetch_subreddits:
            console.print("[yellow]No active source sets found.[/yellow]")
            console.print("Add one with: [cyan]pain-radar sources-add indie_saas[/cyan]")
            raise typer.Exit(1)

    console.print(f"\nFetching posts from {len(fetch_subreddits)} subreddits...")
    console.print(f"  Subreddits: {', '.join(fetch_subreddits[:5])}", end="")
    if len(fetch_subreddits) > 5:
        console.print(f" (+{len(fetch_subreddits) - 5} more)")
    else:
        console.print()

    # Create a minimal settings-like object for the pipeline
    class FetchSettings:
        def __init__(self):
            self.subreddits = fetch_subreddits
            self.listing = settings.listing
            self.posts_per_subreddit = fetch_limit
            self.top_comments = settings.top_comments
            self.max_concurrency = settings.max_concurrency
            self.db_path = path
            self.user_agent = settings.user_agent

    fetch_settings = FetchSettings()

    try:
        result = asyncio.run(run_fetch_only(fetch_settings))
        console.print(f"[green]✓ Fetched {result} posts[/green]")
    except Exception as e:
        console.print(f"[red]Fetch failed:[/red] {e}")
        raise typer.Exit(1) from e
